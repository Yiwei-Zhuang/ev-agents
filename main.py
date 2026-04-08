import json

from langchain_core.messages import HumanMessage, SystemMessage

from agent import ZPAgent


def deepagents_main_loop():
    with open("key.json", "r") as f:
        key = json.load(f)
    agent = ZPAgent("thread_91872", api_key=key["zhipu"])

    inputs = [
        # SystemMessage(content="你是一名精通了c语言的专家"),
        # HumanMessage(content="写一个c语言的hello world，保存到当前路径hello.c中，并将编译方式写到Makefile中去。"),
        # HumanMessage(content="my_day.txt包含了我最近做的事情，帮我整理成日报"),
        # HumanMessage(content="你有哪些skills"),
        HumanMessage(content="今天杭州天气如何，结果直接打出来"),
    ]
    response = agent.invoke(inputs)
    messages = response["messages"]
    for message in messages:
        print(message.content)

    while "__interrupt__" in response:
        interrupt_value = response["__interrupt__"][0].value
        action_requests = interrupt_value["action_requests"]
        review_configs = interrupt_value["review_configs"]
        decisions = []
        print(f"\nInterrupt received!")
        for i in range(len(review_configs)):
            review_config = review_configs[i]
            action_request = action_requests[i]
            print(f"action_name: {review_config["action_name"]}")
            key_params = agent.get_key_params(review_config["action_name"])
            for k, v in action_request["args"].items():
                print(f"{k}: {v}")
            print(f"allowed_decisions: {review_config["allowed_decisions"]}")
            while True:
                usr_decision = input(">")
                if usr_decision in review_config["allowed_decisions"]:
                    decision = {
                        "type": usr_decision,
                        "edited_action": {}
                    }

                    if decision["type"] == "edit":
                        args = {}
                        for key, value in action_request["args"].items():
                            edit_decision = input(f"{key} (enter if not edit):")
                            if edit_decision != "":
                                args[key] = edit_decision
                        decision["edited_action"] = {
                            "name": action_request["name"],  # Must include the tool name
                            "args": args
                        }
                    decisions.append(decision)
                    break

        response = agent.resume(decisions)

    print("hehe")


def print_hi(name):
    # Use a breakpoint in the code line below to debug your script.
    print(f'Hi from {name}')  # Press ⌘F8 to toggle the breakpoint.


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    print_hi("EV")
    deepagents_main_loop()
