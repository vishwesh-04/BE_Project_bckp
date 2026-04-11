# import flwr.superexec.app
# from PySide6.QtCore import QObject, QThread
# from flwr.client import ClientApp, start_client
# from flwr.client.mod.secure_aggregation import secaggplus_mod
#
# from flwr.superexec.app import *
#
# from client.client_app import client_fn
#
#
# class FLClientController(QObject):
#
#     pass
#
# app = ClientApp(client_fn=client_fn, mods=[secaggplus_mod])
#
# class FLClientWorker(QThread):
#
#     def run(self):
#         start_client()