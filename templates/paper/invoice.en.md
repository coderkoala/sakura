+++
title = "Invoice"
about = "a small business's bill with line items, VAT 13% (or --pan-only without VAT), numbered and entered in the register"
items = true
series = "INV"
party = "buyer"

[fields]
seller = {label = "your business (or your name)", me = "business|name", required = true}
seller_address = {label = "its address", me = "business_address|address"}
seller_pan = {label = "your PAN/VAT registration number", me = "pan", required = true}
seller_phone = {label = "your phone", me = "phone"}
buyer = {label = "who is being billed", required = true}
buyer_address = {label = "their address"}
buyer_pan = {label = "their PAN, if they have one"}
payment = {label = "how to pay: Cash, or the bank and account", me = "payment"}
note = {label = "a line under the bill: Goods once sold are not returned"}
+++

# {{seller}}

| {{tax_id_label}}: {{seller_pan}}{{#seller_address}}
| {{seller_address}}{{/seller_address}}{{#seller_phone}}
| Phone: {{seller_phone}}{{/seller_phone}}

## Invoice

| Invoice No.: {{number}}
| Date: {{date_full}}

| Billed to: **{{buyer}}**{{#buyer_address}}
| Address: {{buyer_address}}{{/buyer_address}}{{#buyer_pan}}
| Buyer's PAN: {{buyer_pan}}{{/buyer_pan}}

{{items_table}}

**In words:** {{total_words}}

{{#payment}}Payment: {{payment}}

{{/payment}}{{#note}}{{note}}

{{/note}}| ....................
| For {{seller}}
