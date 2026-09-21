"""Run with Python 3.12: python main.py."""
import logging
import sys
import os
# A stale system proxy (commonly left by a stopped local VPN client) breaks
# cloud providers before the application can reach the active VPN route.
for _proxy_name in ('HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','http_proxy','https_proxy','all_proxy'):
    os.environ.pop(_proxy_name, None)
from logging.handlers import RotatingFileHandler


def main():
    if "--self-test-design" in sys.argv:
        from friday.design_check import run
        return run()
    if "--self-test-pc" in sys.argv:
        from friday.pc_check import run
        return run()
    if "--self-test" in sys.argv:
        from friday.bundle_check import run
        return run()
    from friday.qt import QApplication, QMessageBox, QLocalServer, QLocalSocket
    from friday.storage import Store
    from friday.ui import STYLE, Window
    app = QApplication(sys.argv)
    app.setApplicationName("Пятница")
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    app.setQuitOnLastWindowClosed(False)
    server = QLocalServer(app)
    socket = QLocalSocket()
    socket.connectToServer("FridayAssistantV2")
    if socket.waitForConnected(300):
        socket.write(b"show")
        socket.flush()
        socket.waitForBytesWritten(300)
        return 0
    QLocalServer.removeServer("FridayAssistantV2")
    if not server.listen("FridayAssistantV2"):
        QMessageBox.critical(None, "Пятница", "Не удалось запустить единственный экземпляр приложения.")
        return 1
    try:
        store = Store()
        handler = RotatingFileHandler(store.data / "logs/friday.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        logging.basicConfig(level=logging.INFO, handlers=[handler], format="%(asctime)s %(levelname)s %(message)s")
        window = Window(store)
        def activate():
            connection = server.nextPendingConnection()
            if connection:
                connection.close()
                connection.deleteLater()
            window.reveal()
        server.newConnection.connect(activate)
        window.show()
        result = app.exec()
        server.close()
        return result
    except Exception as exc:
        logging.exception("Startup failed")
        QMessageBox.critical(None, "Не удалось запустить Пятницу", str(exc))
        return 1


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    sys.exit(main())
