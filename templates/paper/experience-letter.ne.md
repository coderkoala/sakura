+++
title = "अनुभव प्रमाणपत्र"
about = "रोजगारदाताले कर्मचारीले कुन पदमा, कहिलेदेखि कहिलेसम्म काम गरेको प्रमाणित गर्ने पत्र"

[fields]
employer = {label = "रोजगारदाता (तपाईंको व्यवसाय)", me = "business", required = true}
employer_address = {label = "त्यसको ठेगाना", me = "business_address|address"}
employee = {label = "कर्मचारीको नाम", required = true}
position = {label = "उहाँको पद", required = true}
from_date = {kind = "date", label = "काम सुरु गरेको मिति", required = true}
to_date = {kind = "date", label = "काम छाडेको मिति", required = true}
remarks = {kind = "para", label = "उहाँको काम र आचरणबारे भन्न चाहेको कुरा"}
signer = {label = "दस्तखत गर्नेको नाम", me = "name", required = true}
signer_position = {label = "दस्तखत गर्नेको पद: प्रबन्ध निर्देशक"}
+++

# {{employer}}

{{#employer_address}}{{employer_address}}

{{/employer_address}}मिति: {{date_full}}

## अनुभव प्रमाणपत्र

जो जससँग सम्बन्ध राख्दछ,

श्री **{{employee}}** ले मिति {{from_date_local}} देखि {{to_date_local}} सम्म {{employer}} मा **{{position}}** पदमा रही काम गर्नुभएको बेहोरा प्रमाणित गरिन्छ।

{{#remarks}}{{remarks}}

{{/remarks}}निजको उज्ज्वल भविष्यको कामना गर्दछौँ।

| ....................
| {{signer}}{{#signer_position}}
| {{signer_position}}{{/signer_position}}
| {{employer}}
