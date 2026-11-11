+++
title = "Application letter"
about = "a formal application or request to an office, a school, a bank or a company"

[fields]
to_title = {label = "who it goes to, by post: The Principal, The Branch Manager", required = true}
to_office = {label = "their office or institution", required = true}
to_address = {label = "its address"}
subject = {label = "the subject line: Request for a character certificate", required = true}
body = {kind = "para", label = "what you are asking and why, in your own words", required = true}
name = {label = "your name", me = "name", required = true}
address = {label = "your address", me = "address"}
phone = {label = "your phone", me = "phone"}
email = {label = "your email", me = "email"}
+++

Date: {{date_full}}

| To,
| {{to_title}}
| {{to_office}}{{#to_address}}
| {{to_address}}{{/to_address}}

**Subject: {{subject}}**

Respected Sir/Madam,

{{body}}

I would be grateful for your kind consideration and the necessary action on this request.

Yours faithfully,

| Signature: ....................
| {{name}}{{#address}}
| {{address}}{{/address}}{{#phone}}
| Phone: {{phone}}{{/phone}}{{#email}}
| Email: {{email}}{{/email}}
