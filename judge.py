import requests
import json
import pandas as pd
from openai import OpenAI
import os
import dotenv
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCaseParams
from deepeval.test_case import LLMTestCase


dotenv.load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

wismo_endpoint = "https://ca-odpr-eus-gt-wismo-dev.agreeableriver-391c9765.eastus.azurecontainerapps.io"
mcp_endpoint = "https://ca-odpr-eus-gt-mcp-dev.agreeableriver-391c9765.eastus.azurecontainerapps.io/mcp"

test_cases = pd.read_csv("wismo_test_cases.csv")

client = OpenAI(api_key=OPENAI_API_KEY)

correctness_metric = GEval(
    name="Correctness",
    evaluation_steps=[
        "Check whether the facts in 'actual output' contradicts any facts in 'expected output'",
        "Do not peaceily compare wording, only check for factual correctness",
        "Make sure that the actual output includes the soldto and soldto number as well as any split orders if applicable",
    ],
    evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT, LLMTestCaseParams.EXPECTED_OUTPUT],
)


# call the endpoint for a specific order number
def get_wismo_endpoint(order_number):
    try:
        url = f"{wismo_endpoint}/order_overview/{order_number}"
        response = requests.get(url)

        return response.json()
    
    except Exception as e:
        return str(e)

# get the AI response from the MCP tool
def get_mcp_response(order_number, client):
    try:
        resp = client.responses.create(
            model="gpt-5",
            instructions="Role & Goal: You are an order-lookup assistant. By default, you return a minimal order header plus any split/backorder levels. You reveal additional details only when the user explicitly asks for them. Always include the split orders and the customer soldto and soldto number",
            tools=[
                {
                    "type": "mcp",
                    "server_label": "dmcp",
                    "server_description": "A MCP server for getting information on orders",
                    "server_url": mcp_endpoint,
                    "require_approval": "never",
                },
            ],
            input=f"Tell me about order {order_number}",
        )

        return resp.output_text
    
    except Exception as e:
        return str(e)
    
def sample_test_cases(test_cases: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    sampled = (
        test_cases
        .groupby(cols, group_keys=False)
        .apply(lambda g: g.sample(n=2, replace=False, random_state=42))
        .reset_index(drop=True)
    )
    return sampled


def evaluate_correctness(row):
    test_case = LLMTestCase(
        input=f"Tell me about order {row['order_number']}",
        actual_output=row['mcp_response'],
        expected_output=json.dumps(row['wismo_response'])
    )
    result = correctness_metric.measure(test_case, client)
    return result


if __name__ == "__main__":
    sampled = sample_test_cases(test_cases, cols=['IsSplitOrder', 'IsDropShip', 'IsOnBackOrder', 'IsInvoiced'])

    # convert order number to int
    sampled['ordernumber'] = sampled['ordernumber'].astype(int)

    # create a table of responses
    responses = pd.DataFrame({  
        "order_number": sampled['ordernumber'],
        "wismo_response": [get_wismo_endpoint(order_number) for order_number in sampled['ordernumber']],
        "mcp_response": [get_mcp_response(order_number, client) for order_number in sampled['ordernumber']]
    })

    evaluation_results = [evaluate_correctness(row) for index, row in responses.iterrows()]

    # save to csv
    results_df = pd.DataFrame(evaluation_results)
    results_df.to_csv("evaluation_results.csv", index=False)

