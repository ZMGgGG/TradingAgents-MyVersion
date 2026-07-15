from langchain_core.messages import HumanMessage, RemoveMessage

from tradingagents.agents.utils.agent_utils import create_msg_delete


def test_parallel_msg_delete_does_not_remove_shared_message_ids():
    delete_messages = create_msg_delete(remove_existing=False)
    message = HumanMessage(content="Analyze BTC")

    result = delete_messages({"messages": [message]})

    assert result == {"messages": []}


def test_serial_msg_delete_deduplicates_remove_operations():
    delete_messages = create_msg_delete(remove_existing=True)
    message = HumanMessage(content="Analyze BTC")
    message.id = "shared-message-id"
    duplicate = HumanMessage(content="Analyze BTC again")
    duplicate.id = "shared-message-id"

    result = delete_messages({"messages": [message, duplicate]})

    removals = [item for item in result["messages"] if isinstance(item, RemoveMessage)]
    assert [item.id for item in removals] == ["shared-message-id"]
