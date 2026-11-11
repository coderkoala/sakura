+++
title = "Request to the ward office"
about = "a complaint or a request to your ward office (a road, a drain, a recommendation letter); an ordinary letter, not the ward's own form"

[fields]
municipality = {label = "the municipality or rural municipality: Kathmandu Metropolitan City", required = true}
ward_no = {label = "the ward number", required = true}
district = {label = "the district"}
subject = {label = "the subject line: Request to repair the road at Shantinagar", required = true}
body = {kind = "para", label = "what is wrong or what you need, where, and since when", required = true}
name = {label = "your name", me = "name", required = true}
address = {label = "your address", me = "address"}
phone = {label = "your phone", me = "phone"}
citizenship_no = {label = "your citizenship certificate number, if the matter needs it"}
+++

Date: {{date_full}}

| To,
| The Ward Chairperson
| Ward No. {{ward_no}} Office, {{municipality}}{{#district}}
| {{district}}{{/district}}

**Subject: {{subject}}**

Respected Sir/Madam,

I submit the following for your attention.

{{body}}

I therefore request the ward office to look into this matter and take the necessary action.

Yours faithfully,

| Signature: ....................
| {{name}}{{#address}}
| {{address}}{{/address}}{{#citizenship_no}}
| Citizenship certificate no.: {{citizenship_no}}{{/citizenship_no}}{{#phone}}
| Phone: {{phone}}{{/phone}}
