+++
title = "Experience letter"
about = "an employer certifying that someone worked there, in what post and between which dates"

[fields]
employer = {label = "the employer (your business)", me = "business", required = true}
employer_address = {label = "its address", me = "business_address|address"}
employee = {label = "the employee's name", required = true}
position = {label = "their post", required = true}
from_date = {kind = "date", label = "first day of work", required = true}
to_date = {kind = "date", label = "last day of work", required = true}
remarks = {kind = "para", label = "anything you want to say about their work and conduct"}
signer = {label = "who signs it", me = "name", required = true}
signer_position = {label = "the signer's post: Managing Director"}
+++

# {{employer}}

{{#employer_address}}{{employer_address}}

{{/employer_address}}Date: {{date_full}}

## Experience Letter

To whom it may concern,

This is to certify that **{{employee}}** worked at {{employer}} as **{{position}}** from {{from_date_local}} to {{to_date_local}}.

{{#remarks}}{{remarks}}

{{/remarks}}We wish them every success in the future.

| ....................
| {{signer}}{{#signer_position}}
| {{signer_position}}{{/signer_position}}
| {{employer}}
