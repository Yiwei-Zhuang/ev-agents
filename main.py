import json

from langchain_core.messages import HumanMessage

from agent import ZPAgent, AgentConfig


def load_api_key(path="key.json"):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)["zhipu"]
    except FileNotFoundError:
        print(f"Error: API key file not found: {path}")
        return None
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {path}: {e}")
        return None
    except KeyError:
        print(f"Error: 'zhipu' key not found in {path}")
        return None


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
    config = AgentConfig(
        model="glm-4.6",
        temperature=0.3,
        base_url="https://open.bigmodel.cn/api/paas/v4/",
    )
    agent = ZPAgent("thread_91872", api_key=load_api_key(), config=config)

    inputs = [
        HumanMessage(
            content="给我写个c语言的hello world"
            # content="当前目录下有些rej文件，帮我删除掉"
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
