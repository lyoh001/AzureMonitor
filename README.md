# VICGOV - Azure Alert, Monitor, Report Workflow
## 1. Introduction
### 1.1	Overview

As a result of needing to improve on cloud monitoring solution, Hosting Platform Services has been working to resolve number of issues and centralizing source of azure monitor via a workflow described in the diagram 2.1. 
 
This document is intended to provide a high level overview of workflow how the events captures and sends out the notifications. 
 
Included in this report is a step by step detailed guide around where to look for troubleshooting.




## 2 Logical Architecture
### 2.1	Logical System Component Overview
![Figure 1: Logical Architecture Overview](./.images/workflow.png)
1. Azure events get triggered and delivered to eventgridtopic.
    - ![Figure 2.1: Step1](./.images/step1.png)

2. From the topic it gets routed to azure queue.

    - ![Figure 2.2: Step1](./.images/step2.png)

3. The function will get invoked and processes the business logic.
It will
    - it stores the event to the db for analysis.
    - it filters and alerts the admins with a notifications.
    - ![Figure 2.3: Step3](./.images/step3.png)

4. Events will be stored in cosmos db for a monthly analysis report.
    - ![Figure 2.4: Step5](./.images/step4.png)

5. Events will be filtered based on the business requirement, then sent to logic app to process the email notifications. 
    - ![Figure 2.5: Step5](./.images/step5.png)

6. The administrators will be notified via email this notification will include 
    - event time 
    - event name 
    - event id 
    - azure resource where the event occurred 
    - user id who triggered the event 
    - event status (success/failure) 
    - subscription name
    - ![Figure 2.6: Step7](./.images/step6.png)