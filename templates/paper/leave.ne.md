+++
title = "बिदाको निवेदन"
about = "कार्यालय वा विद्यालयमा दुई मितिबीचको बिदा माग्ने निवेदन"

[fields]
to_title = {label = "जसलाई लेखिएको हो, पदले: प्रबन्धक, कक्षा शिक्षक", required = true}
to_office = {label = "कार्यालय, कम्पनी वा विद्यालय", required = true}
to_address = {label = "त्यसको ठेगाना"}
from_date = {kind = "date", label = "बिदाको पहिलो दिन", required = true}
to_date = {kind = "date", label = "बिदाको अन्तिम दिन", required = true}
reason = {kind = "para", label = "कारण, एक-दुई वाक्यमा", required = true}
name = {label = "तपाईंको नाम", me = "name", required = true}
position = {label = "तपाईंको पद, वा कक्षा र रोल नम्बर"}
phone = {label = "तपाईंको फोन", me = "phone"}
+++

मिति: {{date_full}}

| श्रीमान् {{to_title}}ज्यू,
| {{to_office}}{{#to_address}},
| {{to_address}}{{/to_address}}।

**विषय: बिदा स्वीकृत गरिदिने सम्बन्धमा।**

महोदय,

उपर्युक्त सम्बन्धमा तल उल्लिखित कारणले गर्दा म मिति {{from_date_local}} देखि {{to_date_local}} सम्म उपस्थित हुन नसक्ने भएकाले उक्त अवधिको बिदा स्वीकृत गरिदिनुहुन विनम्र अनुरोध गर्दछु।

कारण: {{reason}}

निवेदक

| दस्तखत: ....................
| नाम: {{name}}{{#position}}
| पद/कक्षा: {{position}}{{/position}}{{#phone}}
| सम्पर्क नं.: {{phone}}{{/phone}}
