+++
title = "Rent receipt"
about = "a landlord's receipt for rent paid, numbered and entered in the register"
series = "RENT"
party = "tenant"
amount = "amount"

[fields]
landlord = {label = "the landlord (you)", me = "name", required = true}
landlord_address = {label = "your address", me = "address"}
landlord_pan = {label = "your PAN", me = "pan"}
tenant = {label = "who paid the rent", required = true}
property = {label = "the rented place: Flat 2B, Baneshwor-10, Kathmandu", required = true}
period = {label = "what the rent covers: Kartik 2083", required = true}
amount = {kind = "money", label = "how much", required = true}
method = {label = "how it was paid: cash, bank transfer"}
+++

## Rent Receipt

| Receipt No.: {{number}}
| Date: {{date_full}}

Received from **{{tenant}}** the sum of **Rs. {{amount}}** ({{amount_words}}) as rent for **{{property}}** for the period **{{period}}**{{#method}}, paid by {{method}}{{/method}}.

| ....................
| {{landlord}} (landlord){{#landlord_address}}
| {{landlord_address}}{{/landlord_address}}{{#landlord_pan}}
| PAN No.: {{landlord_pan}}{{/landlord_pan}}
