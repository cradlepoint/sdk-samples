# Source Routing (config/routing/tables and config/routing/policies)

Source routing forces traffic from a specific source IP out a specific WAN
device. It takes two objects: a routing table holding the route, and a routing
policy that matches source traffic and points at that table.

**The two objects do NOT share the same identity model.** This is the single
biggest source of bugs in source-routing code.

| | `config/routing/tables` | `config/routing/policies` |
|---|---|---|
| Has `_id_` UUID | Yes | **No** |
| Addressed by | numeric collection index | numeric collection index |
| POST returns | numeric index in `data` | numeric index in `data` |
| Referenced by | its `_id_` UUID (from a policy's `table` field) | nothing references a policy |

Verified against an E3000 on NCOS 7.25.101. The DTD for
`config/routing/policies` lists only `dst_ip_network`, `in_dev`, `ip_version`,
`priority`, `src_ip_network`, `table` — there is no `_id_` child.

## Schema

`config/routing/policies` is an array, `maxlength: 100`:

```json
{
  "ip_version": "ip4",
  "priority": 1,
  "table": "00000001-c598-384f-900b-64c77a24ba67",
  "src_ip_network": "192.0.2.10"
}
```

`config/routing/tables` is an array whose entries DO carry `_id_`:

```json
{
  "_id_": "00000001-c598-384f-900b-64c77a24ba67",
  "name": "MSS-mdm-75613315",
  "routes": [
    {"netallow": false, "ip_network": "0.0.0.0/0",
     "dev": "mdm-75613315", "auto_gateway": true, "distribute": false}
  ]
}
```

## Working create flow

```python
# 1. Create the table. POST returns a numeric collection index.
resp = cp.post('config/routing/tables/', route_table)
table_index = resp.get('data')            # e.g. 1

# 2. GET by that index to read the table's _id_ UUID.
table_obj = cp.get(f'config/routing/tables/{table_index}')
table_id = table_obj.get('_id_')          # e.g. '00000001-c598-...'

# 3. The policy references the table by UUID, NOT by index.
route_policy = {
    'ip_version': 'ip4',
    'priority': 1,
    'table': table_id,
    'src_ip_network': source_ip,
}
resp = cp.post('config/routing/policies/', route_policy)
policy_index = resp.get('data')           # numeric index - this is the ONLY handle

# 4. Verify by content. Do NOT look for policy['_id_'] - it does not exist.
pol_obj = cp.get(f'config/routing/policies/{policy_index}')
verified = all(pol_obj.get(k) == v for k, v in route_policy.items())
```

The two identifiers you keep are deliberately different kinds of thing:

```text
table_id      = routing table _id_ UUID
policy_index  = routing policy numeric collection index
```

## Finding an existing policy

Because there is no `_id_`, match on the policy's contents and remember the
enumerate index:

```python
policies = cp.get('config/routing/policies') or []
policy_index = None
for idx, p in enumerate(policies):
    if isinstance(p, dict) and p.get('table') == table_id:
        policy_index = idx
        break
```

`policy.get('_id_')` always returns `None`. Code that treats that as "not
found" will POST a brand new duplicate policy on every pass, and code that
treats it as a delete handle will silently delete nothing. The policy array caps
at 100 entries, so a loop that re-POSTs each cycle eventually fails outright.

## Deleting: always descending index

Both paths are arrays, so deleting one entry shifts the index of every later
entry. Collect the indexes first, then delete highest to lowest:

```python
stale = [idx for idx, p in enumerate(policies)
         if isinstance(p, dict) and p.get('table') in stale_table_ids]
for idx in sorted(stale, reverse=True):
    cp.delete(f'config/routing/policies/{idx}')
    time.sleep(0.1)
```

Deleting ascending removes the wrong objects and skips others.

Delete the policies **before** the tables they reference, otherwise you leave
policies pointing at a table that no longer exists.

## Deleting a table when you only kept its UUID

Resolve the UUID back to its current index:

```python
def delete_table_by_id(table_id):
    tables = cp.get('config/routing/tables') or []
    for idx, t in enumerate(tables):
        if isinstance(t, dict) and t.get('_id_') == table_id:
            cp.delete(f'config/routing/tables/{idx}')
            return
    cp.delete(f'config/routing/tables/{table_id}')  # compatibility fallback
```

On NCOS 7.25.101 an E3000 accepts `DELETE config/routing/tables/{uuid}` as well
as by index, but index addressing is what works consistently across platforms,
so resolve to an index first and keep the UUID form only as a fallback.

## Main table policy priority

The default `Main` table policy sits at `config/routing/policies/0` with
`priority: 0`. To make your own policies take precedence, raise Main's priority
number (lower number wins), e.g. `cp.put('config/routing/policies/0/priority', 10)`
and give your policies `priority: 1`.

## Avoiding source routing entirely

If you only need a speed test bound to a specific WAN, `control/netperf` takes
an `ifc_wan` field and needs no routing config at all. See the netperf section
in `.kiro/steering/api-reference.md`.

Reference implementation: `apps/Mobile_Site_Survey/Mobile_Site_Survey.py`
(`source_route`, `cleanup_mss_routing`, `_delete_table_by_id`).
