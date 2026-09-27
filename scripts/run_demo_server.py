# coding=utf-8
"""演示/公网隧道用的启动脚本。

与 main.py 的区别（安全相关，勿混用）：

* 显式关闭 debug —— main.py 的 debug=True 会把 Werkzeug 交互式调试器暴露出去，
  经公网隧道等同于开放远程代码执行；
* 启用 ProxyFix，让应用正确识别经 Cloudflare Tunnel 转发后的协议与客户端地址；
* 默认只监听 127.0.0.1（隧道由本机 cloudflared 连入，无需对外暴露端口）；
* 打印实际绑定地址，便于与隧道地址核对。

用法：
    uv run python scripts/run_demo_server.py [端口]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from werkzeug.middleware.proxy_fix import ProxyFix

from app import create_app, db, init_seed_data


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    app = create_app()

    # Cloudflare Tunnel 在 X-Forwarded-* 头里传真实协议与客户端地址
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    with app.app_context():
        db.create_all()
        init_seed_data()

    print(f" * 演示服务已启动：http://127.0.0.1:{port}")
    print(" * debug 已关闭，不会暴露调试器")
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False, threaded=True)


if __name__ == "__main__":
    main()
