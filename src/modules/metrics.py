from prometheus_client import Counter, Histogram
from quart import Quart, jsonify, request
from guilded.ext import commands, tasks
from quart_cors import route_cors

import database as db
import guilded
import time

class Metrics(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        
        self.request_count = Counter(
            'app_request_count',
            'Application Request Count',
            ['method', 'endpoint', 'http_status']
        )
        self.request_latency = Histogram(
            'app_request_latency_seconds',
            'Application Request Latency',
            ['method', 'endpoint']
        )
        self.bot_latency = Histogram(
            'bot_latency_seconds',
            'Bot Latency',
            ['latency']
        )
        self.server_count = Histogram(
            'server_count',
            'Server Count',
            ['count']
        )
        self.user_count = Histogram(
            'user_count',
            'User Count',
            ['count']
        )
        self.verification_count = Counter(
            'verification_count',
            'Verification Count',
            ['count']
        )
    
    async def log_verification(self, server: guilded.Server):
        self.verification_count.inc()
        # TODO: Log to bots analytics for site to use
    
    @tasks.loop(minutes=60)
    async def update_bot_metrics(self):
        self.verification_count.reset()
        try:
            guilds = await db.servers.count_servers()
        except Exception as e:
            print(f"Failed to get server count: {str(e)}")
        else:
            self.server_count.observe(guilds)
        
        try:
            users = await db.users.count_users()
        except Exception as e:
            print(f"Failed to get user count: {str(e)}")
        else:
            self.user_count.observe(users)
    
    @tasks.loop(seconds=5)
    async def update_bot_latency(self):
        self.bot_latency.observe(self.bot.latency * 1000)
    
    def register_routes(self, app: Quart):
        @app.route("/uptime", methods=["GET"])
        @route_cors(allow_methods=["GET"], allow_origin=["*"], allow_credentials=False)
        async def Uptime():
            bot_latency = self.bot.latency * 1000

            return jsonify({
                "bot_latency": bot_latency
            })
        
        @app.before_request
        async def before_request():
            request.start_time = time.time()
        
        @app.after_request
        async def after_request(response):
            request_latency = time.time() - request.start_time
            self.request_latency.labels(request.method, request.path).observe(request_latency)

            self.request_count.labels(request.method, request.path, response.status_code).inc()

            return response

def setup(bot: commands.Bot):
    bot.add_cog(Metrics(bot))