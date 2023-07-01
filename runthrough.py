import registration_api
from pyntree import Node


x = registration_api.API()

token = x.register("jvadair", "jva@jvadair.com", "password")
assert len(registration_api.unverified.where(username="jvadair")) > 0
x.verify(token)
assert len(registration_api.unverified.where(username="jvadair")) == 0
session = {}
resp = x.login(session, "jvadair", "password")
g_id = x.create_group(session['id'], 'testgroup')
n = Node(f'db/groups/{g_id}.pyn')
x.modify_group(g_id, name="agony")
n.file.reload()
o_id = x.create_org(session['id'], 'testorg')
n2 = Node(f'db/orgs/{o_id}.pyn')
x.modify_org(o_id, name="agony")
n2.file.reload()
