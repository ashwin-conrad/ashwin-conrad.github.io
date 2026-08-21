# Projects:
    - Corrosion Coupon Monitoring Dashboard
    - Brazed Aluminium Heat Exchanger Fatigue Analysis and life cycle management
    - Inspection Scope generation tool
    - report building/formatting tool
    - Safety Critical Element Identification and flagging
    - Flaring Volume Estimate Calculator
    - Integrity Inspections Turnaround Planning

### Corrosion Coupon Monitoring Dashboard

* Replaced a decentralized workflow — where operators manually reviewed individual vendor reports with no centralized tracking — with an automated corrosion monitoring pipeline built in Microsoft Fabric.

* Built vendor-specific dataflows in Fabric to clean, transform, and normalize corrosion coupon data from multiple report formats received on 3–6 month inspection cycles, eliminating manual copy-and-paste data handling.

* Implemented a lakehouse-based architecture with semantic models and automated pipelines, where vendor file uploads trigger data refreshes without manual intervention.

* Created a Power BI dashboard tracking 100+ corrosion coupons across 12 facilities, linking coupon metadata, locations, and facility-level corrosion trends.

* Enabled operations and integrity teams to contextualize corrosion trends against operating condition changes and identify when further investigation is required, without manually reviewing raw vendor reports.

***

### Brazed Aluminum Heat Exchanger Fatigue Analysis and Lifecycle Management

* Analyzed 2+ years of historical operating data for 12+ brazed aluminum heat exchangers — approximately half of which had already exceeded their optimal design lifespan with no prior repair work.

* Extracted process data using the PI Historian Excel add-in and developed Python-based screening tools to assess exceedances against OEM-prescribed thermal ramp rates, cyclic operation limits, and parting sheet temperature distributions.

* Identified the need for additional sensor instrumentation on select exchangers where monitoring coverage was insufficient relative to potential failure locations.

* Recommended reducing actuated valve opening rates to limit turbulent flow and erosion on the inner pipe face, reducing ongoing fatigue accumulation.

* Compiled findings into a lifecycle management summary and presented results to leadership to support risk-based decision-making for aging BAHX assets across ALA facilities.

***

### Inspection Scope Generation Tool

* Developed a Python-based inspection scope generation tool using openpyxl and python-docx to automate creation of equipment-specific inspection scopes from AllAssets (IDMS) exports.

* Translated team inspection knowledge, risk model outputs, and IDMS records into reusable logic for generating standardized inspection comments and recommended activities.

* Automated batch generation of scopes across all ALA facilities, reducing initial scope creation time from several minutes per item to seconds per item.

* Generated 500+ inspection scopes saved directly to equipment folders on shared enterprise drives for streamlined inspector review and sign-off.

* Used across all facilities by the integrity team, replacing a manual Power Query and Power BI export workflow with a scalable Python pipeline.

***

### Report Building / Formatting Tool

* Built a modular Python-based report generation tool using python-docx that converts Markdown-formatted technical content into fully formatted Word reports aligned with corporate brand standards.

* Designed a template-driven architecture where any report type can be generated given a heading outline and template, supporting technical engineering reports, assessment summaries, and other deliverables.

* Integrated LLM-assisted drafting to convert preliminary scopes, calculations, and technical context into structured report drafts, with template filling for consistent formatting.

* Reduced report formatting time from hours to days per report depending on length and complexity, particularly for new reports built from scratch.

* Extended the tool to support automated Word, Excel, and PowerPoint deliverable generation, improving consistency across internal engineering documentation.

***

### Safety Critical Element Identification and Flagging

* Flagged 13,000+ assets as Safety Critical Elements across 20 facilities by reviewing equipment functions, Alarm SDKs, and governance documents distinguishing functional vs. inherent safety critical elements.

* Developed structured data workflows to compare asset registers, inspection data, and equipment metadata, identifying gaps and inconsistencies in the management database.

* Created 3,000+ new equipment records for assets identified as missing from the management database, improving data completeness for safety-critical equipment tracking.

* Produced load sheets of tags to be flagged in the system and lists of missing tags requiring creation, enabling systematic SCE classification across all facility systems.

***

### Flaring Volume Estimate Calculator

* Developed a flaring volume estimate calculator driven by AER reporting guidelines to supplement metered data with engineering estimates, giving operators an independent gut-check against meter readings.

* Built a repeatable Excel/Power Query workflow linking flare events to flow, pressure, and equipment metadata for 2 trains at 1 facility.

* Designed the tool to provide independent volume estimates so operations is not strictly reliant on meters, particularly during metering issues or anomalies.

* Structured the calculator to support future integration with PI historian data for more accurate flow rate and pressure inputs.

***

### Integrity Inspections Turnaround Planning

* Supported turnaround planning by compiling inspection requirements, equipment lists, and risk-based inspection intervals for facility assets.

* Coordinated inspection planning data across equipment registers, inspection management systems, and generated scope packages to support pre-turnaround execution readiness.

* Assisted in prioritizing inspection activities by linking inspection scopes to regulated intervals, equipment criticality, and asset integrity requirements.

* Improved planning efficiency by standardizing inspection data inputs and supporting batch generation of inspection documentation for turnaround execution.

***