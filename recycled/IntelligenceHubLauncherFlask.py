import traceback
import threading

from GlobalConfig import DEFAULT_IHUB_PORT
from MyPythonUtility.easy_config import EasyConfig
from Tools.SystemMonotorLauncher import start_system_monitor
from IntelligenceHubStartup import show_intelligence_hub_statistics_forever, wsgi_app, ihub


def startup_with_werkzeug(blocking: bool):
    config = EasyConfig()
    listen_ip = config.get('intelligence_hub_web_service.service.listen_ip', '0.0.0.0')
    listen_port = config.get('intelligence_hub_web_service.service.listen_port', DEFAULT_IHUB_PORT)

    from werkzeug.serving import make_server
    server = make_server(listen_ip, listen_port, wsgi_app)

    if blocking:
        server.serve_forever()
    else:
        server_thread = threading.Thread(target=server.serve_forever)
        server_thread.start()
        # server.shutdown()
        # server_thread.join(timeout=timeout)


def main():
    print("=========================================================================")
    print("================ Default startup with Flask WSGI service ================")
    print("=========================================================================")

    startup_with_werkzeug(blocking=False)       # or app.run(host='0.0.0.0', port=5000, debug=True)
    start_system_monitor()
    show_intelligence_hub_statistics_forever(ihub)


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(str(e))
        print(traceback.format_exc())
