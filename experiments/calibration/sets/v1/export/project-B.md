## Рубрика оцінювання

Шкала 1–5 по кожному критерію. Оцінюється **проєкт цілком**, не окремий блок.

### K1. Узгодженість між артефактами

Чи описують усі артефакти одну й ту саму бізнес-модель. Дивитись: сегмент у карті емпатії ↔ персона в сценарії ↔ customer_segments у канвасі; обрана монетизація ↔ revenue_streams; болі клієнта ↔ ціннісні пропозиції; ключові ресурси ↔ структура витрат; гіпотези ↔ припущення канвасу.

- **1** — артефакти описують фактично різні бізнеси
- **3** — загальна лінія витримана, є одна-дві помітні розбіжності в деталях
- **5** — наскрізна узгодженість, кожен артефакт виводиться з попередніх

### K2. Специфічність

Чи прив'язаний зміст до цієї конкретної ідеї. Робочий тест: підставити іншу ідею з тієї ж галузі — якщо текст лишається доречним, специфічність низька.

- **1** — переважно шаблонні формулювання, ідею можна замінити без шкоди
- **3** — частина змісту прив'язана до ідеї, частина — загальні місця
- **5** — конкретика в усіх артефактах: названі ролі, процеси, обмеження галузі

### K3. Змістовна повнота

Чи розкрито кожен артефакт по суті. Оцінюється не наявність полів (її гарантує схема), а чи несе кожен пункт інформацію.

- **1** — формальне заповнення, пункти-заглушки, дублювання змісту між блоками
- **3** — основні блоки розкрито, окремі поверхові або повторюють сусідні
- **5** — кожен артефакт несе власний зміст, жоден не є переказом іншого

### K4. Економічна правдоподібність

Чи тримається бізнес-логіка. Дивитись: чи є хтось, хто платить; чи співвідносяться витрати й надходження; чи відповідає канал збуту сегменту; чи не суперечить обраний патерн решті моделі.

- **1** — модель не працює економічно
- **3** — життєздатна, але є непроговорене сумнівне припущення
- **5** — економіка узгоджена, ризиковані припущення винесені в гіпотези

### K5. Придатність гіпотез до перевірки

- **1** — гіпотези без критерію перевірки («клієнтам потрібен наш продукт»)
- **3** — конкретні, але спосіб перевірки неочевидний або результат неоднозначний
- **5** — кожна гіпотеза містить перевірюване твердження, зрозумілий експеримент, покрито всі три категорії ризику

### Що НЕ впливає на оцінку

- обсяг тексту (довший артефакт не є кращим)
- впевненість тону
- форматування, структурованість
- граматика й стилістика
- кількість пунктів у блоці (п'ять поверхових гірші за три змістовні)

## Формат відповіді

По кожному з п'яти критеріїв, у порядку, наведеному вище:

1. **Обґрунтування** (2–3 речення) — чому саме такий бал. Це йде ПЕРЕД балом: спершу поясни, потім став оцінку, а не навпаки.
2. **Бал** — ціле число від 1 до 5.
3. **Цитата** — коротка цитата з матеріалу нижче, що підтверджує бал.

Сумарний бал не виводити — жодного середнього чи підсумкового числа по всіх п'яти критеріях.

## Вихідна ідея

Сервіс для приватних клінік окремо організовує післявізитний супровід пацієнтів, який зазвичай залишається розподіленим між лікарем, адміністратором і пацієнтом. Після прийому система формує зрозумілий план наступних дій, нагадує про контрольні процедури та збирає інформацію про самопочуття. Працівники клініки бачать лише ті сигнали, які потребують їхньої уваги, а пацієнт отримує послідовний маршрут між візитами. Рішення може працювати незалежно від медичної інформаційної системи та підключатися до неї лише для отримання необхідних даних.

## Блок: Карта емпатії

**Каже**
- As a clinic administrator, I need every patient to leave with a clear understanding of what to do after the appointment.
- Our doctors should not have to manually chase patients for routine follow-up.
- I need to know which patients require staff attention without reviewing every message or reminder.
- Follow-up responsibilities are currently spread across doctors, reception staff, and patients, so things are easy to miss.

**Думає**
- If post-visit instructions are not followed, the patient may have a worse outcome and blame the clinic.
- We need a consistent follow-up process that works across different doctors and appointment types.
- A separate service must fit our workflows and use only the necessary data from our medical information system.
- Staff time should be reserved for meaningful patient issues rather than routine reminders.

**Робить**
- As a clinic administrator, I coordinates follow-up tasks between doctors, administrators, and patients after appointments.
- I asks staff to call or message patients about control procedures, tests, and repeat visits.
- I monitors whether patients have received instructions and escalates cases when concerns are reported.
- I manages fragmented information from appointment notes, phone calls, messages, and staff handoffs.

**Відчуває**
- I feel responsible when a patient does not understand or complete the recommended next steps.
- I feel frustrated by repetitive manual reminders and unclear ownership of follow-up work.
- I feel anxious that an important patient signal could be missed among routine communications.
- I feel pressure to improve patient experience without adding unnecessary workload for clinicians.

**Болі**
- Post-visit follow-up is fragmented between the doctor, clinic administrator, and patient, with no single coordinated route.
- Routine reminders for examinations, procedures, and return visits consume staff time and are inconsistently delivered.
- Patient-reported wellbeing information can arrive late, through different channels, or not reach the right staff member.
- It is difficult to distinguish routine patient communication from signals that genuinely require clinical or administrative attention.
- Existing medical information systems may not provide a simple, dedicated workflow for patient support between visits.

**Вигоди**
- I want each patient to receive a simple, sequential post-visit plan that explains the next actions and timing.
- I want automated reminders to help patients complete control procedures and follow-up appointments on time.
- I want a focused view of only those patient responses or wellbeing signals that need staff intervention.
- I want clinicians and administrators to have clear responsibility boundaries while maintaining continuity for the patient.
- I want a follow-up service that can operate independently while connecting to the medical information system only when needed.

## Блок: Варіанти бізнес-моделі

### Subscription · CareRoute
- Аудиторія: Private outpatient clinics with recurring follow-up needs across multiple physicians and administrators
- Ціннісна пропозиція: Give every patient an automated, understandable post-visit route while routing only actionable wellbeing signals to clinic staff.
- Опис: Clinics pay a recurring per-clinic or per-active-patient subscription for automated care plans, reminders, patient check-ins, and an exception dashboard. It directly addresses pain #1 (fragmented follow-up), pain #2 (manual reminders), and pain #4 (difficulty separating routine communication from actionable signals), while delivering gains #1, #2, and #3. An independent deployment with limited medical-information-system data exchange also supports gain #5.
- Монетизація: subscription
- Ключова метрика: MRR and net revenue retention
- Час до цінності: 1 business day to launch the first post-visit pathway and send the first automated reminder
- Оцінка: 92 — High: recurring follow-up is an ongoing operational workflow, making predictable subscription pricing natural and closely aligned with the core fragmented-process and staff-time pains. Value can be demonstrated rapidly through reminders and triaged responses, although integration and clinical workflow adoption can slow expansion.

### Transaction Fee · CareRoute Actions
- Аудиторія: Small private clinics and specialty practices that want to pay only for completed patient follow-up journeys
- Ціннісна пропозиція: Pay only when the service executes a defined post-visit follow-up journey that keeps a patient on track and surfaces exceptions.
- Опис: The clinic is charged per activated or completed follow-up journey, such as a post-procedure recovery sequence, diagnostic-test reminder sequence, or return-visit pathway. This monetizes the clinic's need to reduce pain #2 (repetitive manual reminders) and pain #1 (split ownership) while providing gain #1 (a sequential patient plan) and gain #2 (timely automated reminders). It lowers adoption friction for smaller clinics, but the unit of value can be harder to define when patients need variable levels of contact.
- Монетизація: transaction_fee
- Ключова метрика: Follow-up journey GMV and effective take rate
- Час до цінності: 30 minutes to activate the first patient follow-up journey after template setup
- Оцінка: 68 — Moderate: pay-per-journey pricing offers a clear low-commitment entry point for clinics uncertain about volume. It is weaker than subscription because follow-up is continuous operational infrastructure rather than a discrete transaction, and usage-based bills may discourage broad patient enrollment.

### Retainer Plus SaaS · CareRoute Managed
- Аудиторія: Multi-specialty private clinics with high patient volumes and limited capacity to manage follow-up exceptions
- Ціннісна пропозиція: Combine a dedicated follow-up platform with an expert operations team that keeps patient pathways running and escalates only cases requiring clinic attention.
- Опис: The clinic pays an annual software fee plus a monthly managed-service retainer for pathway design, onboarding, monitoring, and agreed first-line patient coordination. This directly addresses pain #3 (wellbeing information arriving late or to the wrong staff member), pain #4 (lack of signal triage), and gain #4 (clear responsibility boundaries), while retaining the independent, selectively integrated approach in gain #5. It is suited to clinics that want continuity between visits without adding routine workload to physicians or administrators.
- Монетизація: retainer_plus_saas
- Ключова метрика: Annual contract value and renewal rate
- Час до цінності: 2 weeks to configure priority care pathways and begin managed exception handling
- Оцінка: 85 — Strong: the managed layer directly relieves staffing pressure and makes escalation workflows credible for complex, high-volume clinics. It scores below pure SaaS because service delivery increases operational cost, requires clear clinical responsibility boundaries, and can constrain scalability.

## Блок: Бізнес-модель канвас

**Ключові партнери**
- Private-clinic clinical leaders and administrators who define approved post-visit pathways, escalation rules, and staff ownership.
- Medical information system and EHR vendors for limited, consented exchange of appointment, patient, and follow-up data.
- Secure messaging providers (SMS, email, and patient messaging channels) for delivery of reminders and check-ins.

**Ключові активності**
- Configure specialty- and visit-specific post-visit pathways with next actions, due dates, reminders, and escalation thresholds.
- Automatically send patient care plans, control-procedure reminders, return-visit prompts, and wellbeing check-ins.
- Triage patient responses into an exception dashboard so staff review actionable signals rather than every routine message.
- Onboard clinics and selectively integrate only the minimum required medical-information-system data.

**Ключові ресурси**
- Care-pathway engine that converts visit outcomes into sequential patient actions, schedules, reminders, and check-ins.
- Clinic-facing exception dashboard with configurable wellbeing signals, routing rules, and audit history.
- Secure patient communication infrastructure, consent controls, and minimal-data integration connectors.
- Pathway templates and implementation expertise for recurring follow-up use cases in private outpatient clinics.

**Ціннісні пропозиції**
- A clear, sequential post-visit route gives each patient understandable next actions and timing, addressing fragmented follow-up ownership and the need for a single coordinated plan.
- Automated reminders for tests, procedures, and return visits reduce repetitive staff outreach while helping patients complete recommended actions on time.
- Wellbeing check-ins and exception triage surface only patient signals requiring clinical or administrative attention, reducing the risk that important concerns are missed.
- An independent follow-up service can fit existing clinic workflows and connect to the medical information system only for necessary data.

**Відносини з клієнтами**
- Guided onboarding to launch the first approved post-visit pathway and automated reminder within 1 business day for the subscription offering.
- Self-service clinic administration for pathway templates, staff roles, escalation thresholds, and exception-dashboard review.
- For managed-service clients, an agreed operations team supports pathway design, monitoring, and first-line coordination while escalating defined cases to clinic staff.

**Канали**
- Direct B2B sales to private-clinic owners, administrators, medical directors, and operations leaders.
- Pilot deployments built around a high-volume follow-up workflow, such as post-procedure recovery, diagnostic testing, or repeat-visit reminders.
- Referrals and implementation partnerships with medical information system vendors and clinic workflow consultants.

**Сегменти клієнтів**
- Private outpatient clinic administrators responsible for coordinating post-visit tasks across doctors, reception staff, and patients.
- Private clinics with recurring follow-up needs across multiple physicians and administrators, where routine reminders currently consume staff time.
- Multi-specialty private clinics with high patient volumes and limited capacity to monitor follow-up exceptions internally.

**Структура витрат**
- Software development, hosting, security, consent management, and maintenance of the independent follow-up platform and exception dashboard.
- Variable communication costs for SMS, email, and messaging volume, which scale with active patients and activated follow-up journeys.
- Clinic onboarding, pathway configuration, support, and limited medical-information-system integration work.
- Managed-service operations staff for pathway design, monitoring, and first-line coordination under retainer-plus-SaaS contracts.

**Потоки доходів**
- Recurring per-clinic or per-active-patient subscription for care plans, reminders, patient check-ins, and the exception dashboard; tracked through MRR and net revenue retention.
- Transaction fee per activated or completed defined follow-up journey, such as a post-procedure, diagnostic-test, or return-visit sequence; tracked through follow-up journey GMV and effective take rate.
- Annual software fee plus monthly managed-service retainer for pathway design, onboarding, monitoring, and agreed first-line coordination; tracked through annual contract value and renewal rate.

## Блок: Архітектура моделі

**Епіцентр:** offer_driven

The differentiation is centered in the value_propositions section: a coordinated sequential patient route, automated reminders, and wellbeing check-ins that triage only actionable exceptions for clinic staff. The key_resources and key_activities—care-pathway engine, exception dashboard, messaging, and limited MIS integration—primarily support delivery of that distinct post-visit follow-up offer. Customer segments are conventional private clinics, and the revenue streams use standard subscription, usage, and service-retainer mechanisms rather than being the principal innovation.

**Патерн:** unbundling

The canvas separates a post-visit customer-relationship workflow that has traditionally been combined with clinical consultation and clinic administration. The service specializes in patient communication, reminders, check-ins, and exception routing, while clinics and clinicians retain responsibility for care decisions and escalated cases; this division is reflected in key_activities, customer_relationships, and the managed-service option. It is not a multi-sided platform because EHR vendors, messaging providers, and consultants are key partners rather than interdependent paying customer groups, and no free or partner-led open-model economics are defined.

## Блок: Альтернативи (What-If)

### Productized Self-Service Follow-Up SaaS
Make CareRoute a fast-to-adopt, standardized subscription product for small and mid-sized clinics, prioritizing template-led self-service over labor-intensive managed operations and bespoke integration.

- **eliminate** (customer_relationships): For managed-service clients, an agreed operations team supports pathway design, monitoring, and first-line coordination while escalating defined cases to clinic staff. — Removing the managed-service relationship keeps the operating model software-led and avoids service delivery costs that conflict with a scalable self-service bet.
- **reduce** (key_activities): Onboard clinics and selectively integrate only the minimum required medical-information-system data. -> Provide a lightweight, no-code onboarding flow and optional CSV/API import for only essential appointment and patient-contact data; defer bespoke integrations until expansion. — A narrower integration scope reduces implementation time and makes a low-friction subscription viable for clinics with limited IT capacity.
- **raise** (revenue_streams): Recurring per-clinic or per-active-patient subscription for care plans, reminders, patient check-ins, and the exception dashboard; tracked through MRR and net revenue retention. -> Tiered recurring per-clinic or per-active-patient subscription with a free implementation-light starter tier, standardized pathway limits, and paid upgrades for volume, channels, and advanced triage; tracked through MRR, activation rate, and net revenue retent — Strengthening subscription packaging creates predictable revenue and gives clinics a clear path from a low-risk initial deployment to broader usage.
- **create** (key_resources): A library of pre-approved, specialty-specific pathway templates with plain-language patient instructions, default reminder cadences, and configurable non-clinical escalation rules. — A reusable template library enables clinics to launch quickly without depending on custom pathway design or managed operations.

Очікуваний ефект: Lower sales and onboarding friction, faster time to first live pathway, and improved SaaS gross margins; the trade-off is reduced fit for complex clinics needing hands-on coordination.

### Premium Managed Continuity Service
Concentrate on high-volume, multi-specialty clinics that will pay for an accountable managed follow-up layer, using the platform as infrastructure for human-supported patient continuity and clinically governed escalation.

- **eliminate** (revenue_streams): Transaction fee per activated or completed defined follow-up journey, such as a post-procedure, diagnostic-test, or return-visit sequence; tracked through follow-up journey GMV and effective take rate — Eliminating per-journey billing avoids incentives to limit enrollment and supports comprehensive, continuous follow-up under a higher-value service contract.
- **reduce** (customer_relationships): Self-service clinic administration for pathway templates, staff roles, escalation thresholds, and exception-dashboard review. -> Restricted clinic self-service for viewing exceptions, approving pathway changes, and managing designated escalation contacts; CareRoute operations configures and monitors core workflows. — Reducing self-service shifts operational complexity away from clinic staff and makes the managed-service promise more credible.
- **raise** (customer_relationships): For managed-service clients, an agreed operations team supports pathway design, monitoring, and first-line coordination while escalating defined cases to clinic staff. -> A dedicated managed-continuity team provides pathway design, daily exception monitoring, documented first-line patient coordination, service-level response targets, and escalation to named clinic owners under agreed clinical boundaries. — A stronger human service layer directly addresses clinics' staffing constraints and their need to ensure significant patient signals receive attention.
- **create** (key_resources): A clinically governed operations playbook covering response scripts, escalation severity levels, handoff protocols, service-level targets, and audit-ready supervision for managed follow-up teams. — A formal operations playbook makes managed coordination repeatable, safer, and easier for clinics to trust at scale.

Очікуваний ефект: Higher annual contract value, stronger retention, and more differentiated outcomes for complex clinics, offset by higher staffing, governance, and delivery costs.

### Connected Follow-Up Network
Shift from the current unbundled, single-sided clinic SaaS model toward a multi-sided platform: clinics initiate care routes, while verified diagnostic providers, home-care services, and pharmacies fulfill patient next steps and compete for qualified referrals. This explicitly changes the architecture pattern to a two-

- **reduce** (channels): Direct B2B sales to private-clinic owners, administrators, medical directors, and operations leaders. -> Targeted direct sales focused on anchor clinics and specialties that can seed local follow-up demand, supplemented by partner-led acquisition. — The network model needs a smaller number of anchor clinics rather than a broad, fully direct sales motion for every customer.
- **raise** (key_partners): Medical information system and EHR vendors for limited, consented exchange of appointment, patient, and follow-up data. -> Medical information system and EHR vendors for consented exchange of appointment, patient, follow-up, referral-status, and completed-service data, supported by co-selling and certified integration partnerships. — Deeper interoperability is needed to close the loop between a clinic's recommended action and a partner's fulfillment status.
- **create** (customer_segments): Verified diagnostic centers, laboratories, pharmacies, rehabilitation providers, and home-care providers seeking qualified, consented patient referrals from participating clinics. — Adding a provider-side customer group establishes the second side required for a genuine multi-sided follow-up network.
- **create** (revenue_streams): Partner subscription and success-based referral fees from verified fulfillment providers for qualified, consented bookings or completed follow-up services, with clinics retaining core platform access. — Provider-funded economics monetize fulfilled next steps and can subsidize adoption for anchor clinics without charging patients for routing.
- **create** (value_propositions): Patients can move from a clinic recommendation to a verified, bookable follow-up service in one guided route, while clinics receive confirmation of completion and partners receive qualified consented‑ — This creates a network-specific value proposition that neither the existing reminder product nor a single clinic alone can provide.

Очікуваний ефект: Potentially lower clinic acquisition friction and new referral-based revenue, with stronger patient completion data; however, it introduces marketplace liquidity, consent, neutrality, and partner-quality risks.

## Блок: Гіпотези

- **[desirability / q1]** In interviews and paid-pilot offers with 12 private outpatient clinic administrators, at least 8 will commit to enrolling at least 70% of eligible patients in a 60-day post-visit follow-up pilot after seeing the care-plan, reminder, and exception-dashboard workflow; fewer than 8 commitments would invalidate the assumption that coordinated follow-up is a must
- **[viability / q1]** At least 5 of 10 private clinics completing a 30-day pilot will sign or provide a written procurement commitment for a recurring subscription priced at no less than $300 per clinic per month or $1 per active follow-up patient per month; fewer than 5 will invalidate subscription willingness to pay for the current offer.
- **[feasibility / q1]** Against a clinically reviewed test set of at least 200 de-identified patient check-in responses, configurable escalation rules will route at least 95% of expert-labeled actionable signals to the designated clinic queue within 15 minutes and will miss 0 responses labeled urgent; performance below either threshold will invalidate the safety and usefulness of a
- **[feasibility / q1]** For at least 4 of 5 pilot clinics, the team can launch one approved post-visit pathway using only a CSV import or minimal API fields (patient contact, visit date, pathway type, and responsible staff member) within 1 business day, without a bespoke medical-information-system integration; fewer than 4 launches will invalidate the independent-deployment promise
- **[desirability / q2]** Among at least 300 patients enrolled in live follow-up pathways, at least 70% will open the first post-visit plan within 48 hours and at least 50% will confirm completion of one requested next action before its due date; results below either threshold will invalidate the assumption that patients will use the sequential digital route rather than rely on staff
- **[viability / q3]** When shown both pricing options after a pilot, at least 30% of 10 small clinics will prefer a per-activated-follow-up-journey fee over a recurring subscription, while accepting a fee of at least $3 per journey; fewer than 3 clinics meeting both conditions will invalidate transaction-fee pricing as a meaningful secondary revenue stream.

## Блок: Сценарій використання

**Персона:** Clinic Administrator — Clinic administrator at a private outpatient clinic
Біль: Post-visit follow-up is fragmented between the doctor, clinic administrator, and patient, with no single coordinated route.

**Часова шкала:**
- [context] After a busy afternoon of appointments, the clinic administrator finds that one patient has not booked a required control procedure, another has sent a wellbeing concern through a different channel, and no one clearly owns the next follow-up step.
- [goal] The clinic administrator wants every patient to leave with a clear next-action plan while ensuring staff spend time only on follow-up cases that require attention.
- [action] The administrator activates a CareRoute post-visit pathway that sends each patient a plain-language sequential care plan, automated procedure and return-visit reminders, and a wellbeing check-in, with configured rules routing concerning responses to the exception dashboard.
- [result] Patients receive an understandable route with due dates and reminders, while the administrator sees only actionable missed steps or wellbeing signals in one focused queue instead of reviewing every routine message.
- [impact] Follow-up ownership becomes visible and consistent across doctors, administrators, and patients, reducing manual outreach and lowering the risk that an important patient concern is missed between visits.

**До:** $0 per month — Monthly recurring revenue (MRR) from the follow-up service
**Після:** $600 per month — Monthly recurring revenue (MRR) from the follow-up service

## Блок: Презентація (Pitch)

**Для інвестора:**
- *hook* — **Between visits, patient care too often falls through the cracks**: CareRoute turns fragmented post-visit coordination into a clear patient route and a focused exception queue for private clinics.
- *problem* — **Clinics spend staff time chasing routine follow-up**: Post-visit follow-up is fragmented between doctors, administrators, and patients; routine reminders are inconsistently delivered, while important wellbeing signals can arrive late, through different channels, or miss the right staff member.
- *solution* — **Automate the routine. Surface the exceptions.**: CareRoute delivers sequential care plans, reminders for tests and return visits, and wellbeing check-ins, then routes only actionable signals to staff. It operates independently and connects to the medical information system only for necessary data.
- *traction* — **A $600 MRR clinic can prove value from day one**: Example potential: one clinic moves from $0 to $600 MRR after launching its first pathway, with first reminder live within 1 business day. The subscription model tracks MRR and net revenue retention as clinics expand active patient enrollment.
- *ask* — **Raising $500K to validate repeatable clinic adoption**: Funds will de-risk viability and feasibility through 10 paid pilots, safety testing on 200 de-identified check-in responses, and minimal-data launches at 5 clinics within 1 business day. The target is 5 subscription commitments at $300+ per clinic per month or $1 per active follow-up patient.

**Для клієнта:**
- *opening* — **Stop ending each day with scattered follow-up loose ends**: After busy appointments, a missed control procedure, a wellbeing message in another channel, and unclear ownership should not become your team’s next emergency.
- *empathy* — **You need clarity without adding work for clinicians**: “Our doctors should not have to manually chase patients for routine follow-up.” You feel responsible when patients miss next steps and anxious that an important signal may be lost in routine communication.
- *transformation* — **Give every patient a route—and your team one focused queue**: Activate a plain-language post-visit plan with due dates, automated reminders, and wellbeing check-ins. Instead of reviewing every message, your staff sees actionable missed steps and concerning responses in one place.
- *social_proof* — **Example: launch fast, reduce routine outreach**: Example: a clinic launches its first approved pathway within 1 business day and earns $600 in monthly recurring revenue from the service. A 60-day pilot can target enrollment of at least 70% of eligible follow-up patients.
- *invitation* — **Launch one high-volume follow-up pathway this week**: Start with post-procedure recovery, diagnostic testing, or return-visit reminders using a CSV import or minimal API fields. Book a workflow review to define your plan, escalation rules, and responsible staff members.
