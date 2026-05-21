import os
import json
import requests
import pandas as pd
from datasets import Dataset
from openai import OpenAI
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall
from ragas.llms import llm_factory
from ragas.embeddings import HuggingFaceEmbeddings
from dotenv import load_dotenv
import time
from tqdm import tqdm
from ragas.run_config import RunConfig

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

BACKEND_URL = "http://16.171.177.101:8081/chat"
GEMINI_MODEL = "gemini-3.1-flash-lite"

def get_rag_response(question):
    try:
        response = requests.post(BACKEND_URL, json={"query": question})
        response.raise_for_status()
        data = response.json()

        answer = data.get("reply", "")
        contexts = [cite.get("text", "") for cite in data.get("citations", [])]

        return answer, contexts
    except Exception as e:
        print(f"Error calling backend for question '{question}': {e}")
        return "", []

def main():
    test_set_path = os.path.join(os.path.dirname(__file__), "test_set.json")
    with open(test_set_path, "r") as f:
        test_data = json.load(f)

    print(f"Running evaluation on {len(test_data)} questions...")

    results = []
    for item in tqdm(test_data, desc="Evaluating"):
        question = item["question"]
        ground_truth = item["ground_truth"]

        answer, contexts = get_rag_response(question)

        results.append({
            "question": question,
            "answer": answer,
            "contexts": contexts,
            "ground_truth": ground_truth
        })
        time.sleep(2)

    df = pd.DataFrame(results)
    dataset = Dataset.from_pandas(df)

    gemini_client = OpenAI(
        api_key=os.getenv("GEMINI_API_KEY"),
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
    )
    llm = llm_factory(GEMINI_MODEL, client=gemini_client, max_tokens=8192)

    embeddings = HuggingFaceEmbeddings(model="sentence-transformers/all-mpnet-base-v2")

    print("\nCalculating Ragas metrics...")
    run_config = RunConfig(max_workers=1, max_retries=10)
    score = evaluate(
        dataset,
        metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
        llm=llm,
        embeddings=embeddings,
        run_config=run_config
    )

    print("\nEvaluation Results:")
    print(score)

    score_df = score.to_pandas()
    output_path = os.path.join(os.path.dirname(__file__), "evaluation_results.csv")
    score_df.to_csv(output_path, index=False)
    print(f"Detailed results saved to '{output_path}'")

if __name__ == "__main__":
    if not os.getenv("GEMINI_API_KEY"):
        print("Error: GEMINI_API_KEY not found in environment.")
    else:
        main()
