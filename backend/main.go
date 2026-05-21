package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/joho/godotenv"
	"github.com/rs/cors"
)

type ChatRequest struct {
	Query string `json:"query"`
}

type Citation struct {
	Text   string `json:"text"`
	Page   int    `json:"page"`
	Source string `json:"source"`
}

type ChatResponse struct {
	Reply     string     `json:"reply"`
	Citations []Citation `json:"citations"`
}

func main() {
	if err := godotenv.Load(); err != nil {
		log.Println("No .env file found; using system environment")
	}

	mux := http.NewServeMux()
	mux.HandleFunc("/chat", handleChat)
	mux.HandleFunc("/health", healthCheck)

	handler := cors.Default().Handler(mux)

	port := os.Getenv("PORT")
	if port == "" {
		port = "8081"
	}

	server := &http.Server{
		Addr:         ":" + port,
		Handler:      handler,
		ReadTimeout:  15 * time.Second,
		WriteTimeout: 60 * time.Second,
		IdleTimeout:  120 * time.Second,
	}

	stop := make(chan os.Signal, 1)
	signal.Notify(stop, os.Interrupt, syscall.SIGTERM)

	go func() {
		log.Printf("Starting backend server on port %s...", port)
		if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("could not start server: %v", err)
		}
	}()

	<-stop
	log.Println("Received termination signal, shutting down gracefully...")

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	if err := server.Shutdown(ctx); err != nil {
		log.Fatalf("Server forced to shutdown: %v", err)
	}
	log.Println("Server exiting")
}

func healthCheck(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	w.Write([]byte(`{"status":"ok"}`))
}

func handleChat(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var req ChatRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	embedding, err := getEmbedding(req.Query)
	if err != nil {
		http.Error(w, "Failed to get embedding: "+err.Error(), http.StatusInternalServerError)
		return
	}

	matches, err := searchSupabase(embedding)
	if err != nil {
		http.Error(w, "Failed to call Supabase: "+err.Error(), http.StatusInternalServerError)
		return
	}

	if len(matches) == 0 {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(ChatResponse{
			Reply:     "I couldn't find relevant information in the provided documents.",
			Citations: []Citation{},
		})
		return
	}

	contextText, citations := buildContext(matches)
	reply, err := callGemini(contextText, req.Query)
	if err != nil {
		http.Error(w, "Failed to generate response: "+err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(ChatResponse{
		Reply:     reply,
		Citations: citations,
	})
}

func getEmbedding(text string) ([]float64, error) {
	embedReqBody, _ := json.Marshal(map[string]string{"text": text})

	embedURL := os.Getenv("EMBED_URL")
	if embedURL == "" {
		embedURL = "http://localhost:8001"
	}

	embedRes, err := http.Post(embedURL, "application/json", bytes.NewBuffer(embedReqBody))
	if err != nil {
		return nil, err
	}
	defer embedRes.Body.Close()

	var embedData struct {
		Embedding []float64 `json:"embedding"`
	}
	if err := json.NewDecoder(embedRes.Body).Decode(&embedData); err != nil {
		return nil, err
	}
	return embedData.Embedding, nil
}

type matchResult struct {
	Content  string `json:"content"`
	Metadata struct {
		Page   int    `json:"page"`
		Source string `json:"source"`
	} `json:"metadata"`
	Similarity float64 `json:"similarity"`
}

func searchSupabase(embedding []float64) ([]matchResult, error) {
	supabaseURL := os.Getenv("SUPABASE_URL")
	supabaseKey := os.Getenv("SUPABASE_SERVICE_ROLE_KEY")

	rpcBody, _ := json.Marshal(map[string]interface{}{
		"query_embedding": embedding,
		"match_count":     10,
		"match_threshold": 0.30,
		"filter":          map[string]interface{}{},
	})

	req, err := http.NewRequest("POST", supabaseURL+"/rest/v1/rpc/match_documents", bytes.NewBuffer(rpcBody))
	if err != nil {
		return nil, err
	}
	req.Header.Set("apikey", supabaseKey)
	req.Header.Set("Authorization", "Bearer "+supabaseKey)
	req.Header.Set("Content-Type", "application/json")

	res, err := http.DefaultClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer res.Body.Close()

	var matches []matchResult
	if err := json.NewDecoder(res.Body).Decode(&matches); err != nil {
		return nil, err
	}
	return matches, nil
}

func buildContext(matches []matchResult) (string, []Citation) {
	var contextText string
	var citations []Citation

	for i, m := range matches {
		contextText += fmt.Sprintf("--- Snippet %d ---\n%s\n", i+1, m.Content)
		citations = append(citations, Citation{
			Text:   m.Content,
			Page:   m.Metadata.Page,
			Source: m.Metadata.Source,
		})
	}
	return contextText, citations
}

func callGemini(contextText, query string) (string, error) {
	prompt := fmt.Sprintf("You are an assistant. Answer the user's question based ONLY on the provided context snippets. Do not make up facts. Format with Markdown.\n\nContext:\n%s\n\nUser Question: %s", contextText, query)
	geminiKey := os.Getenv("GEMINI_API_KEY")
	geminiURL := "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent?key=" + geminiKey

	reqBody, _ := json.Marshal(map[string]interface{}{
		"contents": []map[string]interface{}{
			{
				"parts": []map[string]interface{}{
					{"text": prompt},
				},
			},
		},
	})

	var gemData map[string]interface{}
	maxRetries := 3

	for attempt := 1; attempt <= maxRetries; attempt++ {
		res, err := http.Post(geminiURL, "application/json", bytes.NewBuffer(reqBody))
		if err != nil {
			if attempt == maxRetries {
				return "", err
			}
			time.Sleep(time.Duration(attempt) * time.Second)
			continue
		}

		resBytes, _ := io.ReadAll(res.Body)
		res.Body.Close()

		json.Unmarshal(resBytes, &gemData)

		if errMap, hasError := gemData["error"].(map[string]interface{}); hasError {
			if code, ok := errMap["code"].(float64); ok && code == 503 {
				if attempt == maxRetries {
					return "", fmt.Errorf("service unavailable")
				}
				time.Sleep(time.Duration(attempt) * time.Second)
				continue
			}
			return "", fmt.Errorf("API error: %v", errMap)
		}
		break
	}

	reply := "Could not generate response."
	if candidates, ok := gemData["candidates"].([]interface{}); ok && len(candidates) > 0 {
		if cand, ok := candidates[0].(map[string]interface{}); ok {
			if content, ok := cand["content"].(map[string]interface{}); ok {
				if parts, ok := content["parts"].([]interface{}); ok && len(parts) > 0 {
					if part, ok := parts[0].(map[string]interface{}); ok {
						if text, ok := part["text"].(string); ok {
							reply = text
						}
					}
				}
			}
		}
	}
	return reply, nil
}
