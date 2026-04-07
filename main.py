from langchain_core.messages import HumanMessage, SystemMessage

from agent import ZPAgent

ZHIPU_API_KEY = "967bec67178e4222b62af22179f19bff.s9ZaTfZBFne5kAyY"


def test_ai():
    agent = ZPAgent("thread_91872")

    inputs = [
        SystemMessage(content="你是一名精通了c语言的专家"),
        HumanMessage(content="写一个c语言的hello world，保存到当前路径hello.c中，并将编译方式写到Makefile中去。"),
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
        # TODO: if it is edit decision
        # decisions = [{
        #     "type": "edit",
        #     "edited_action": {
        #         "name": action_request["name"],  # Must include the tool name
        #         "args": {"to": "team@company.com", "subject": "...", "body": "..."}
        #     }
        # }]
        print(f"\nInterrupt received!")
        for i in range(len(review_configs)):
            review_config = review_configs[i]
            action_request = action_requests[i]
            print(f"action_name: {review_config["action_name"]}")
            key_params = agent.get_key_params(review_config["action_name"])
            for k, v in action_request["args"].items():
                if k in key_params:
                    print(f"{k}: {v}")
            print(f"allowed_decisions: {review_config["allowed_decisions"]}")
            while True:
                usr_decision = input(">")
                if usr_decision in review_config["allowed_decisions"]:
                    print(f"\nResuming with Command(resume={usr_decision})...")
                    decisions.append({"type": usr_decision})
                    break

        response = agent.resume(decisions)

    print("hehe")


def print_hi(name):
    # Use a breakpoint in the code line below to debug your script.
    print(f'Hi, {name}')  # Press ⌘F8 to toggle the breakpoint.


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    print_hi("EV")
    test_ai()

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
