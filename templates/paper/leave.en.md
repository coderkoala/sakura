+++
title = "Leave request"
about = "asking an employer or a school for leave between two dates"

[fields]
to_title = {label = "who it goes to, by post: The Manager, The Class Teacher", required = true}
to_office = {label = "the office, company or school", required = true}
to_address = {label = "its address"}
from_date = {kind = "date", label = "first day of leave", required = true}
to_date = {kind = "date", label = "last day of leave", required = true}
reason = {kind = "para", label = "the reason, in a sentence or two", required = true}
name = {label = "your name", me = "name", required = true}
position = {label = "your post, or class and roll number"}
phone = {label = "your phone", me = "phone"}
+++

Date: {{date_full}}

| To,
| {{to_title}}
| {{to_office}}{{#to_address}}
| {{to_address}}{{/to_address}}

**Subject: Application for leave**

Respected Sir/Madam,

I respectfully request leave from {{from_date_local}} to {{to_date_local}}, both days included, for the following reason.

{{reason}}

I request you to kindly grant me leave for this period.

Yours faithfully,

| Signature: ....................
| {{name}}{{#position}}
| {{position}}{{/position}}{{#phone}}
| Phone: {{phone}}{{/phone}}
