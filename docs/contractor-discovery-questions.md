# Contractor discovery — questions to pin down what we build

Purpose: talk to the contractors who will actually use this, and come back knowing
exactly what to build, for whom, and what "good" means. Ordered roughly as an
interview. The ★ items are the ones most likely to change the product; get those
answered even if the conversation is short.

Keep asking "walk me through the last real job" — concrete beats hypothetical.

---

## A. Who they are & the job to be done
1. What's your role, and who on the team would actually use this tool day to day?
2. ★ Walk me through the last utility line you planned, start to finish. What did you
   receive, what did you produce, how long did it take, where did time go?
3. How many of these plans do you do a week/month? Are they mostly similar or all different?
4. What does a *bad* day look like — where do plans go wrong or get rejected/reworked?

## B. Inputs — what they start from
5. ★ Which utility do **you** install (telecom/fiber, power, water, gas, sewer, drainage,
   multiple)? New line, replacement, or diversion?
6. ★ Where does your **base map** come from — a commissioned topo survey, an LTA/agency
   drawing, something else? What format (DWG version? DGN? PDF?) and is it reliably in SVY21?
7. ★ Which **third-party plans** do you gather, and from whom (SP PowerGrid, City Energy,
   PUB, Singtel/NetLink/StarHub/M1, LTA, others)? How do you request them, and what do
   they come as — vector PDF, scanned PDF, DWG, shapefile?
8. How current/accurate are those plans, in your experience? Do you already treat some
   providers as unreliable?
9. Do you ever get site survey / detection results (LCDW/TCDW marks, GPR, trial-hole
   findings) as data you'd want the tool to use?
10. Roughly how big is a typical job's area/length?

## C. Outputs — what they must deliver
11. ★ What is the **final deliverable**, exactly? A DWG for submission? To whom (which
    agency/portal), in what format/version, and against what layer & attribute standard?
12. ★ Besides the drawing, what written output is required — method statement, RA/RAMS,
    cost estimate, submission forms? Who signs/stamps it (PE, RTO, Registered Surveyor)?
13. Do you present **alternatives** to anyone (client, agency), or just one chosen design?
    If alternatives — on what basis do you/they choose?
14. What does the drawing need to show beyond the new line — chambers, crossings, trial-hole
    locations, sections/long-profiles, clearances, phasing?

## D. The routing decision — the core of the tool
15. ★ When you decide *where* to put the line, what actually drives it? (existing utilities,
    clearances, road-opening rules, land ownership, depth, future works, client preference…)
16. ★ What are your **clearance rules**, and where do they come from (which code of practice
    per utility)? Are they hard limits or judgement calls?
17. What **depth/cover** do you design to, and does depth ever change the horizontal route?
18. ★ Open-cut vs **trenchless (HDD/pipe-jacking)** — when do you choose each? Do you own
    or sub the boring rig? What length/cost makes boring worth it?
19. When you must **cross** a live line, what actually happens (permits, standby, hand-dig,
    who's notified)? How much does one crossing add in time/cost/risk?
20. What makes one route "easier" than another in your words — and what makes one "cheaper"?
    Are those ever the same route?

## E. Cost & effort — so the optimiser reflects reality
21. ★ How do you **price** a job today? What are the big cost drivers (per-metre trench,
    surface reinstatement by type, traffic management, crossings, chambers, boring, labour)?
22. Can you share indicative rates (or ranges) for: open-cut per m by surface (verge /
    footpath / carriageway), HDD per m, a chamber, a live-line crossing, traffic management?
23. What non-dollar factors matter — programme/time, safety/risk, disruption, weather,
    working hours (night work)? How do you weigh them against cost?

## F. Workflow, roles & compliance
24. ★ Map the real process and approvals: obtaining plans → notifications → detection
    (LCDW/TCDW) → trial holes → design approval → construction → as-built. Who does each,
    and how long does each take?
25. Which **agencies/permits** gate the job (LTA road opening, PUB, SLA, NParks, etc.)?
    What do they require from the plan?
26. What standards must you comply with (SS 576, per-utility codes, SLA survey spec)? Any
    that trip people up?
27. What has to be true for a plan to be **accepted first time** by the reviewer/agency?

## G. Current tools & pain
28. ★ What do you use today (AutoCAD/Civil 3D, MicroStation, QGIS, Excel, by hand)? Which
    step is the most manual/painful/slow?
29. Where do mistakes happen most, and what do they cost when they do?
30. Have you tried anything to automate this? What worked / didn't?

## H. Fit, integration & data
31. What CAD/GIS must the output drop into cleanly? Any house layer standards/templates?
32. How do you exchange files today (email, portal, shared drive)? Any data-security/
    confidentiality constraints on the provider plans? (Several are marked confidential.)
33. Would you use SLA's **Digital Underground / USSP** data directly if available, or do you
    expect to keep working from provider PDFs for the next few years?

## I. Value & commercial
34. ★ If this tool saved you X on a plan, what's X — hours, dollars, avoided rework?
35. What would make you *not* trust or adopt it? (e.g. any auto-routing near live lines
    without human sign-off?)
36. How would you want to pay (per plan, per seat, subscription), and who signs off on buying?
37. How much of the plan are you comfortable with the tool *doing* vs *proposing* for you
    to approve? Where's the line?

## J. Success criteria
38. Six months in, how would you know this tool was worth it? Give one concrete measure.
39. What's the single feature that, if missing, makes this useless to you?

---

### How answers map to the build
- **B, C** → the ingestion + CAD-output specs (formats, layers, attributes, submission target).
- **D, E** → the conflict model, clearance config, and the cost/effort/HDD optimiser weights.
- **F, G** → the method-statement template and where the human-in-the-loop gates sit.
- **H, I, J** → integration, the source-adapter (PDF now / USSP later), pricing, and the
  scope line between "propose" and "do".
