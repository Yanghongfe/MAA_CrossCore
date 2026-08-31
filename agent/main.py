import sys

from maa.agent.agent_server import AgentServer
from maa.toolkit import Toolkit

import my_action
import my_reco
import number_lt  # noqa: F401  # 注册 number_lt 自定义识别
import order_fetch  # noqa: F401  # 注册 取下一单、输入当前UID
from arena_loop import ArenaLoop
from chip_filter_flow import ChipFilterFlow
from weekly_complete import WeeklyFlow


AgentServer.custom_action("arena_loop")(ArenaLoop)
AgentServer.custom_action("chip_filter_flow")(ChipFilterFlow)
AgentServer.custom_action("weekly_flow")(WeeklyFlow)

print("[agent] custom actions ready: 取下一单, 输入当前UID, 取下一待删好友, 删除登记完成")


def main():
    Toolkit.init_option("./")

    if len(sys.argv) < 2:
        print("Usage: python main.py <socket_id>")
        print("socket_id is provided by AgentIdentifier.")
        sys.exit(1)
        
    socket_id = sys.argv[-1]

    AgentServer.start_up(socket_id)
    AgentServer.join()
    AgentServer.shut_down()


if __name__ == "__main__":
    main()
