import json

from langchain_core.messages import HumanMessage, SystemMessage

from agent import ZPAgent


def load_api_key(path="key.json"):
    with open(path) as f:
        return json.load(f)["zhipu"]


def collect_decision(action_request, review_config, agent):
    print(f"action_name: {review_config['action_name']}")
    agent.get_key_params(review_config["action_name"])
    for k, v in action_request["args"].items():
        print(f"{k}: {v}")
    print(f"allowed_decisions: {review_config['allowed_decisions']}")

    while True:
        usr_decision = input(">")
        if usr_decision not in review_config["allowed_decisions"]:
            continue
        decision = {"type": usr_decision, "edited_action": {}}
        if decision["type"] == "edit":
            args = {}
            for key, value in action_request["args"].items():
                edit_decision = input(f"{key} (enter if not edit):")
                if edit_decision != "":
                    args[key] = edit_decision
            decision["edited_action"] = {
                "name": action_request["name"],
                "args": args,
            }
        return decision


def handle_interrupts(agent, response):
    while "__interrupt__" in response:
        interrupt_value = response["__interrupt__"][0].value
        action_requests = interrupt_value["action_requests"]
        review_configs = interrupt_value["review_configs"]
        print("\nInterrupt received!")
        decisions = [
            collect_decision(ar, rc, agent)
            for ar, rc in zip(action_requests, review_configs)
        ]
        response = agent.resume(decisions)
    return response


def deepagents_main_loop():
    agent = ZPAgent("thread_91872", api_key=load_api_key())

    inputs = [
        HumanMessage(
            content="给我写个c语言的hello world"
            # content="/Users/yiweizhuang/cold/poc_test 目录下有两个patch，帮我在那个git项目下合入一下"
        ),
    ]
    response = agent.invoke(inputs)
    for message in response["messages"]:
        print(message.content)

    handle_interrupts(agent, response)

    print("hehe")


def print_hi(name):
    print(f"Hi from {name}")


if __name__ == "__main__":
    print_hi("EV")
    deepagents_main_loop()
