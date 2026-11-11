+++
title = "Authorization letter"
about = "lets someone act for you in one matter (collect a document, sign for a parcel); a plain letter, not a registered power of attorney"

[fields]
name = {label = "your name", me = "name", required = true}
address = {label = "your address", me = "address"}
id_no = {label = "your citizenship or ID number", me = "citizenship_no"}
agent = {label = "who you are authorizing", required = true}
agent_address = {label = "their address"}
agent_id_no = {label = "their citizenship or ID number"}
purpose = {kind = "para", label = "what they may do for you: collect my transcript from the campus", required = true}
valid_until = {kind = "date", label = "the last day it holds"}
phone = {label = "your phone", me = "phone"}
+++

## Authorization Letter

Date: {{date_full}}

To whom it may concern,

I, **{{name}}**{{#address}}, of {{address}}{{/address}}{{#id_no}} (ID no. {{id_no}}){{/id_no}}, authorize **{{agent}}**{{#agent_address}}, of {{agent_address}}{{/agent_address}}{{#agent_id_no}} (ID no. {{agent_id_no}}){{/agent_id_no}}, to act on my behalf in the following matter.

{{purpose}}

{{#valid_until}}This authorization holds until {{valid_until_local}}. {{/valid_until}}Whatever the authorized person does within this matter shall be treated as done by me.

| Signature: ....................
| {{name}}{{#phone}}
| Phone: {{phone}}{{/phone}}

| Signature of the authorized person: ....................
| {{agent}}
