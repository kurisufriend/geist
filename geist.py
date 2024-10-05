import websockets, json, threading, asyncio, time
from random import choice
from ircked.bot import irc_bot
from ircked.message import *

class geist():
    def __init__(self, config_path = "./config.json"):
        # prevent namecollides with a hypothetical USERS message handler
        self.iirc_users = set()
        self.topic = ""

        # maps remote_address -> (connection, nick)
        self.geist_users = {}

        # message bus for calling async functions from non-async ones.
        #  fmt: [(function, (args,))]
        self.ws_bus = []

        with open(config_path, "r") as f:
            self.config = json.loads(f.read())

        self.bot = irc_bot(self.config["irc_nick"], 
            "geist", 
            choice(["blinky", "pinky", "inky", "clyde"])) # ;^)
        
    async def run(self):
        self.bot.connect_register(self.config["irc_server"], self.config["irc_port"])
        def irc_handler(msg, ctx):
            #print("<<", str(msg))
            handler = getattr(self, "irc_"+msg.command.lower(), None)
            try: handler(msg, ctx)
            except TypeError:
                print("unhandled IRC message:", str(msg))
        threading.Thread(target=self.bot.run, args=(irc_handler,)).start()
        await self.ws_run()

    # woo woo woo woo stayin' alive
    def irc_ping(self, msg, ctx):
        self.bot.sendraw(message.manual("", "PONG", msg.parameters))

    # 001 is basically ON_READY. join up w the squad.
    def irc_001(self, msg, ctx):
        self.bot.sendraw(message.manual("", "JOIN", [self.config["irc_channel"]]))
    
    # reply to NAMES, params are a list of all the names
    def irc_353(self, msg, ctx):
        # get rid of the leading colon & meta stuff
        names = self._helper_trim_param_errata(msg.parameters)
        names[0] = names[0][1:]
        # filter out ops of all sorts and voices
        #  some ircds probably have more goofy role symbols but i frankly don't care
        for i in range(len(names)):
            for r in ["@", "+", "%", "&", "~"]:
                names[i] = names[i].replace(r, "")
        # add all these guys to our set
        for n in names:
            self.iirc_users.add(n)
    
    # end of NAMES. catch it and pass so it doesn't pollute the console.
    def irc_366(self, msg, ctx): pass

    # reply to TOPIC, the topic is the param list
    def irc_332(self, msg, ctx):
        ps = self._helper_trim_param_errata(msg.parameters)
        if len(ps) > 0:
            ps[0] = ps[0][1:]
            self.topic = " ".join(ps)
        else:
            self.topic = ""
    
    # when someone else sets a topic. same fmt as 332 p much, so call that.
    def irc_topic(self, msg, ctx):
        self.irc_332(msg, ctx)

    def irc_join(self, msg, ctx):
        # the nick that joined
        nick = msg.prefix[1:].split("!")[0]
        # us joining the desired channel. take names!
        if nick == self.config["irc_nick"]:
            self.iirc_users = set()
            self.bot.socket.send(f"NAMES {msg.parameters[0][1:]}\r\n".encode("utf-8"))
        else:
            # otherwise, add the newbie
            self.iirc_users.add(nick)
        # update iusers
        self._helper_buscall(self.ws_iusers, ())
        
    def irc_part(self, msg, ctx):
        # the nick that left
        nick = msg.prefix[1:].split("!")[0]
        # bye bye
        self.iirc_users.remove(nick)
        # update iusers
        self._helper_buscall(self.ws_isusers, ())

    def irc_privmsg(self, msg, ctx):
        # we're being queried by aliens. assume a suitable disguise.
        if "\x01VERSION\x01" in msg.parameters:
            self.bot.sendraw(message.manual(":"+msg.parameters[0], "PRIVMSG", [msg.prefix[1:].split("!")[0], ":\x01dorfl/geist\x01"]))
            return
        
        # we got a message!!!!
        pm = privmsg.parse(msg)
        if pm.bod == ";info":
            self.bot.sendraw(privmsg.build(ctx.nick, pm.to, "geist running on"+self.config["geist_hostname"]).msg)
        else:
            self.ws_imsg(pm)
    async def ws_run(self):
        async def ws_handler(ws):
            while True:
                try: msg = await ws.recv()
                except websockets.ConnectionClosedOK:
                    await self.ws_closedconn(ws)
                    break

                j = self._helper_verify_ws_msg(msg)
                # if j is a str, the deserialization errored out. tell the client!
                if type(j) == str:
                    await ws.send(self._helper_ws_msg("error", j))
                    await ws.close(1002, j)
                    return
                
                if self.geist_users.get(ws.remote_address) == None and j["type"] != "hi":
                    await ws.send(self._helper_ws_msg("error", "first send a hi message"))
                    continue

                # at this point we're sure it's a properly formed message
                handler = getattr(self, "wsh_"+j["type"], None)
                try: await handler(ws, j)
                except TypeError:
                    print("unhandled ws message:", msg)
                except:
                    await ws.send(self._helper_ws_msg("error", "error while processing command"+msg))
                    await ws.close(1002)
                    return

                print(msg)
        async with websockets.serve(ws_handler, "", self.config["ws_port"]):
            await asyncio.get_running_loop().create_future()
        asyncio.get_event_loop().create_task(self.ws_churn_bus)

    async def ws_closedconn(self, ws):
        # remove the client from the users, then update the user list
        self.geist_users.pop(ws.remote_address)
        await self.ws_gusers()

    # send everyone a gusers update
    async def ws_gusers(self):
        users = [self.geist_users[k][1] for k in self.geist_users.keys()]
        await self._helper_ws_sendall(
            self._helper_ws_msg("gusers", {"who": users})
        )
    
    # send everyone an iusers update
    async def ws_iusers(self):
        users = list(self.iirc_users)
        await self._helper_ws_sendall(
            self._helper_ws_msg("iusers", {"who": users})
        )
    
    # send everyone an imsg (unless we sent it)
    async def ws_imsg(self, irc_pm):
        contents = irc_pm.bod
        author = irc_pm.fr.split("!")[0]
        if author != self.config["irc_nick"]:
            await self._helper_ws_sendall(
                self._helper_ws_msg("imsg", {"author": author, "contents": contents})
            )
        self._helper_append_backlog("imsg", author, contents)
    
    # client introduction (p much just nick registration)
    async def wsh_hi(self, ws, j):
        users = [self.geist_users[k][1] for k in self.geist_users.keys()]
        if j["data"]["nick"] in users:
            err = "nick already in use"
            await ws.send(self._helper_ws_msg("error", err))
            await ws.close(1002, err)
            return
        self.geist_users[ws.remote_address] = (ws, j["data"]["nick"])
        await self.ws_gusers()
        with open(self.config["backlog_json_path"], "r") as f:
            blj = json.loads(f.read())
        ws.send(
            self._helper_ws_msg("orientation",
                {
                    "backlog":  blj,
                    "channel":  self.config["irc_channel"],
                    "topic":    self.topic,
                    "iusers":   list(self.iirc_users),
                    "gusers":   [self.geist_users[k][1] for k in self.geist_users.keys()]
                }
            )
        )
    
    # mirror geist messages to IRC
    async def wsh_gmsg(self, ws, j):
        pm = privmsg.build(
            self.config["irc_nick"], 
            self.config["irc_channel"], 
            f'<{j["data"]["author"]}> {j["data"]["contents"]}'
        )

        self.bot.sendraw(pm.msg)
        self._helper_append_backlog("gmsg", j["data"]["author", j["data"]["contents"]])

    # loop forever, calling functions from the message bus
    async def ws_churn_bus(self):
        while True:
            for m in self.ws_bus:
                function = m[0]
                args = m[1] # should be an unpackable tuple
                function(*args)
            asyncio.sleep(1)

    # add function to ws_bus
    #  takes function reference and tuple args
    def _helper_buscall(self, function, args):
        self.ws_bus.append((function, args))

    # sometimes messages have random bullshit we don't want before the first colon-param
    def _helper_trim_param_errata(self, params):
        res = []
        flip = False
        for i in params:
            if i.startswith(":"): flip = True
            if flip: res.append(i)
        return res

    # ensure websocket messages comply with our format as outlined in readme.txt
    #  return a json object if compliant, the error if not
    def _helper_verify_ws_msg(self, msg):
        try: j = json.loads(msg)
        except:
            return f"message {msg} malformed. JSON expected."
        if j.get("type") == None or j.get("data") == None:
            return f"message {msg} malformed. JSON must have fields 'type' and 'data'."
        return j
    
    # pass a string type and dict data to be serialized for your sending pleasure
    def _helper_ws_msg(self, type, data):
        return json.dumps({"type": type, "data": data})

    # send a message to all connected users
    async def _helper_ws_sendall(self, msg):
        for k in self.geist_users.keys():
            conn = self.geist_users[k][0]
            await conn.send(msg)
    
    # append message to the backlog.
    def _helper_append_backlog(self, type, author, contents):
        with open(self.config["backlog_json_path"], "r") as f:
            j = json.loads(f.read())
        j.append(
            {"type": type, "data": {"author": author, "contents": contents, "time": int(time.time())}}
        )
        # only save the last 100 messages. for perf and ephemerality reasons.
        if len(j) > 100:
            j = j[-100:]
        with open(self.config["backlog_json_path"], "w") as f:
            f.write(json.dumps(j))