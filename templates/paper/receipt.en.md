+++
title = "Receipt"
about = "a receipt for money received, with the amount in words, numbered and entered in the register"
series = "RCT"
party = "received_from"
amount = "amount"

[fields]
issuer = {label = "your business (or your name)", me = "business|name", required = true}
issuer_address = {label = "its address", me = "business_address|address"}
issuer_pan = {label = "your PAN", me = "pan"}
received_from = {label = "who paid", required = true}
amount = {kind = "money", label = "how much", required = true}
purpose = {label = "what it was for: Invoice INV-2083/84-0007, advance for furniture", required = true}
method = {label = "how it was paid: Cash, cheque no. 123456, bank transfer"}
receiver = {label = "who signs for it", me = "name"}
+++

# {{issuer}}

{{#issuer_address}}{{issuer_address}}

{{/issuer_address}}{{#issuer_pan}}PAN No.: {{issuer_pan}}

{{/issuer_pan}}## Receipt

| Receipt No.: {{number}}
| Date: {{date_full}}

| Received from: **{{received_from}}**
| Amount: **Rs. {{amount}}**
| In words: {{amount_words}}
| For: {{purpose}}{{#method}}
| Paid by: {{method}}{{/method}}

The amount above has been received with thanks.

| ....................
| Received by{{#receiver}}: {{receiver}}{{/receiver}}
