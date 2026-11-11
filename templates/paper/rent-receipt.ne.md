+++
title = "घरभाडा रसिद"
about = "घरधनीले भाडा बुझेको रसिद, नम्बर सहित र अभिलेखमा दर्ता"
series = "RENT"
party = "tenant"
amount = "amount"

[fields]
landlord = {label = "घरधनी (तपाईं)", me = "name", required = true}
landlord_address = {label = "तपाईंको ठेगाना", me = "address"}
landlord_pan = {label = "तपाईंको स्थायी लेखा नम्बर (PAN)", me = "pan"}
tenant = {label = "भाडा बुझाउनेको नाम", required = true}
property = {label = "भाडामा दिइएको ठाउँ: फ्ल्याट २ख, बानेश्वर-१०, काठमाडौँ", required = true}
period = {label = "कुन अवधिको भाडा: २०८३ कात्तिक महिना", required = true}
amount = {kind = "money", label = "रकम", required = true}
method = {label = "भुक्तानीको माध्यम: नगद, बैंक ट्रान्सफर"}
+++

## घरभाडा रसिद

| रसिद नं.: {{number}}
| मिति: {{date_full}}

श्री **{{tenant}}** बाट **{{property}}** को **{{period}}** को घरभाडा बापत **रु. {{amount}}** (अक्षरेपी: {{amount_words}}){{#method}} {{method}} मार्फत{{/method}} बुझिलिएँ।

| ....................
| घरधनीको दस्तखत
| नाम: {{landlord}}{{#landlord_address}}
| ठेगाना: {{landlord_address}}{{/landlord_address}}{{#landlord_pan}}
| स्थायी लेखा नं. (PAN): {{landlord_pan}}{{/landlord_pan}}
