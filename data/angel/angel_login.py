from SmartApi import SmartConnect
import pyotp
import time


class AngelSession:

    def __init__(self, api, client, pwd, totp):
        self.api_key = api
        self.client = client
        self.pwd = pwd
        self.totp = totp

    def login(self):

        while True:
            try:
                obj = SmartConnect(api_key=self.api_key)
                otp = pyotp.TOTP(self.totp).now()

                data = obj.generateSession(
                    self.client, self.pwd, otp
                )

                jwt = data["data"]["jwtToken"]
                feed = data["data"]["feedToken"]

                print("Angel login success")
                return obj, jwt, feed

            except Exception as e:
                print("Retry login", e)
                time.sleep(5)
