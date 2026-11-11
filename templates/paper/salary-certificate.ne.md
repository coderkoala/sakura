+++
title = "तलब प्रमाणपत्र"
about = "रोजगारदाताले कर्मचारीको पद र मासिक तलब प्रमाणित गर्ने पत्र (बैंक, भिसा, घरधनीका लागि)"

[fields]
employer = {label = "रोजगारदाता (तपाईंको व्यवसाय)", me = "business", required = true}
employer_address = {label = "त्यसको ठेगाना", me = "business_address|address"}
employee = {label = "कर्मचारीको नाम", required = true}
position = {label = "उहाँको पद", required = true}
joined = {kind = "date", label = "नियुक्ति भएको मिति", required = true}
salary = {kind = "money", label = "मासिक तलब", required = true}
signer = {label = "दस्तखत गर्नेको नाम", me = "name", required = true}
signer_position = {label = "दस्तखत गर्नेको पद: प्रबन्ध निर्देशक"}
+++

# {{employer}}

{{#employer_address}}{{employer_address}}

{{/employer_address}}मिति: {{date_full}}

## जो जससँग सम्बन्ध राख्दछ

श्री **{{employee}}** मिति {{joined_local}} देखि {{employer}} मा **{{position}}** पदमा कार्यरत रहनुभएको र निजको मासिक तलब **रु. {{salary}}** (अक्षरेपी: {{salary_words}}) रहेको बेहोरा प्रमाणित गरिन्छ।

यो प्रमाणपत्र निजको अनुरोधमा जारी गरिएको हो।

| ....................
| {{signer}}{{#signer_position}}
| {{signer_position}}{{/signer_position}}
| {{employer}}
