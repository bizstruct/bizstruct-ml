## Рубрика оцінювання

Шкала 1–5 по кожному критерію. Оцінюється **проєкт цілком**, не окремий блок.

### K1. Узгодженість між артефактами

Чи описують усі артефакти одну й ту саму бізнес-модель. Дивитись: сегмент у карті емпатії ↔ персона в сценарії ↔ customer_segments у канвасі; обрана монетизація ↔ revenue_streams; болі клієнта ↔ ціннісні пропозиції; ключові ресурси ↔ структура витрат; гіпотези ↔ припущення канвасу.

- **1** — артефакти описують фактично різні бізнеси
- **3** — загальна лінія витримана, є одна-дві помітні розбіжності в деталях
- **5** — наскрізна узгодженість, кожен артефакт виводиться з попередніх

### K3. Змістовна повнота

Чи розкрито кожен артефакт по суті. Оцінюється не наявність полів (її гарантує схема), а чи несе кожен пункт інформацію.

- **1** — формальне заповнення, пункти-заглушки, дублювання змісту між блоками
- **3** — основні блоки розкрито, окремі поверхові або повторюють сусідні
- **5** — кожен артефакт несе власний зміст, жоден не є переказом іншого

### K5. Придатність гіпотез до перевірки

- **1** — гіпотези без критерію перевірки («клієнтам потрібен наш продукт»)
- **3** — конкретні, але спосіб перевірки неочевидний або результат неоднозначний
- **5** — кожна гіпотеза містить перевірюване твердження, зрозумілий експеримент, покрито всі три категорії ризику

### K2. Специфічність

Чи прив'язаний зміст до цієї конкретної ідеї. Робочий тест: підставити іншу ідею з тієї ж галузі — якщо текст лишається доречним, специфічність низька.

- **1** — переважно шаблонні формулювання, ідею можна замінити без шкоди
- **3** — частина змісту прив'язана до ідеї, частина — загальні місця
- **5** — конкретика в усіх артефактах: названі ролі, процеси, обмеження галузі

### K4. Економічна правдоподібність

Чи тримається бізнес-логіка. Дивитись: чи є хтось, хто платить; чи співвідносяться витрати й надходження; чи відповідає канал збуту сегменту; чи не суперечить обраний патерн решті моделі.

- **1** — модель не працює економічно
- **3** — життєздатна, але є непроговорене сумнівне припущення
- **5** — економіка узгоджена, ризиковані припущення винесені в гіпотези

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

Сервіс допомагає невеликим пасікам окремо контролювати стан кожного вулика за показниками ваги, температури та вологості.

## Блок: Карта емпатії

**Каже**
- As a small-scale beekeeper, I need to know which individual hive needs attention before the problem becomes visible from the outside.
- I cannot open every hive every day just to check whether the colony is doing well.
- A sudden change in hive weight could mean a swarm, honey flow, or an issue that I should investigate.
- I want clear information about temperature and humidity in each hive, not general assumptions about the whole apiary.

**Думає**
- If I could track each hive separately, I could react earlier to colony problems and avoid unnecessary inspections.
- Different hives can behave very differently, even when they stand in the same apiary.
- I need to distinguish normal seasonal changes in weight from signals that require an immediate visit.
- Temperature and humidity trends may reveal brood or ventilation issues before I notice them during a manual inspection.

**Робить**
- The small-scale beekeeper visits the apiary and visually inspects hives whenever time, weather, and distance allow.
- The small-scale beekeeper opens selected hives to assess colony activity, food stores, brood conditions, and moisture.
- The small-scale beekeeper compares observations between hives using memory, handwritten notes, or irregular records.
- The small-scale beekeeper responds to visible signs such as weak activity, condensation, unexpected lightness, or swarming behavior.

**Відчуває**
- The small-scale beekeeper feels uncertain when a hive cannot be checked regularly.
- The small-scale beekeeper feels worried that a hidden issue in one colony may be discovered too late.
- The small-scale beekeeper feels frustrated when inspections take time but still provide only a snapshot of hive conditions.
- The small-scale beekeeper feels responsible for keeping every colony healthy through changing weather and seasons.

**Болі**
- The small-scale beekeeper lacks continuous, hive-level visibility into changes in weight, temperature, and humidity.
- Manual inspections are time-consuming, can disturb bees, and cannot be performed frequently for every hive.
- Without individual measurements, the small-scale beekeeper may miss early indicators of swarming, food shortages, excess moisture, or abnormal colony activity.
- Conditions can vary between individual hives, making a single observation or general apiary assessment unreliable.
- The small-scale beekeeper has difficulty recognizing meaningful trends because observations are infrequent and not consistently recorded.

**Вигоди**
- The small-scale beekeeper wants a separate, understandable view of weight, temperature, and humidity for every hive.
- The small-scale beekeeper wants early signals of unusual changes so that inspections can be prioritized where they are most needed.
- The small-scale beekeeper wants to reduce unnecessary hive openings while maintaining confidence in colony conditions.
- The small-scale beekeeper wants historical measurements that make seasonal patterns and abnormal deviations easier to identify.
- The small-scale beekeeper wants to make timely, evidence-based decisions that support healthier colonies and more predictable apiary management.

## Блок: Варіанти бізнес-моделі

### Subscription · HivePulse
- Аудиторія: Small-scale beekeepers managing 5–50 hives who need individual, remote visibility across their apiary
- Ціннісна пропозиція: A per-hive monitoring subscription turns weight, temperature, and humidity readings into clear alerts and trends so beekeepers inspect the right hive at the right time.
- Опис: Beekeepers pay a monthly or annual fee per connected hive for dashboards, historical data, seasonal baselines, and anomaly alerts. It directly addresses pain #1 (no continuous hive-level visibility), pain #2 (time-consuming inspections), and pain #5 (inconsistent trend recognition), while delivering gains #1, #2, and #4 through an understandable view for every hive. This is the strongest fit because ongoing sensor data and alerts create recurring value throughout the season.
- Монетизація: subscription
- Ключова метрика: MRR
- Час до цінності: 30 minutes after connecting the first hive sensor
- Оцінка: 92 — High: recurring per-hive monitoring maps directly to the core need for continuous individual measurements and prioritized inspections. The main constraint is hardware installation and seasonal usage patterns, which can increase churn outside active beekeeping periods.

### Transaction Fee · HivePulse Market
- Аудиторія: Small-scale beekeepers purchasing compatible hive scales, temperature/humidity sensors, replacement parts, and monitoring add-ons for individual hives
- Ціннісна пропозиція: A curated marketplace lets beekeepers buy compatible monitoring equipment and installation services for each hive with confidence.
- Опис: The platform takes a commission from each sale of compatible sensors, scales, connectivity devices, and optional installation services. It supports pain #1 by making hive-level measurement equipment easier to obtain and gain #1 by enabling separate readings for each hive; it can also support gain #2 when buyers add alert-capable devices. The fit is weaker than a subscription because one-time equipment purchases do not by themselves solve the need to interpret trends or decide when to inspect.
- Монетизація: transaction_fee
- Ключова метрика: GMV
- Час до цінності: 3 days to receive a recommended compatible monitoring kit
- Оцінка: 61 — Moderate: equipment purchasing is necessary for monitoring, and a trusted compatibility layer reduces adoption friction for small apiaries. However, marketplace liquidity, supplier relationships, and hardware margins make it less directly aligned with the ongoing visibility and decision-support pain.

### Retainer Plus SaaS · HivePulse Care
- Аудиторія: Small-scale beekeepers with 10–50 hives who want remote monitoring plus expert-guided prioritization of inspections
- Ціннісна пропозиція: A managed monitoring service combines per-hive data with regular expert review so beekeepers know which colony needs attention and why.
- Опис: Customers pay an annual or seasonal retainer covering sensor setup, SaaS access, and scheduled review of unusual weight, temperature, and humidity changes, with escalation recommendations when thresholds or trends warrant inspection. It addresses pain #3 (missed early indicators), pain #4 (differences between hives), and pain #5 (difficulty recognizing meaningful trends), while delivering gains #2 and #5 through prioritized, evidence-based action. This model suits beekeepers who value confidence and support but may be too expensive for the smallest hobby apiaries.
- Монетизація: retainer_plus_saas
- Ключова метрика: ACV
- Час до цінності: 7 days after installation for the first reviewed hive-status report
- Оцінка: 78 — Strong: expert interpretation makes sensor data more actionable and directly reduces uncertainty around abnormal changes. Its score is below the pure subscription model because recurring human support raises delivery costs and narrows affordability for small-scale beekeepers.

## Блок: Бізнес-модель канвас

**Ключові партнери**
- Hive-scale, temperature, and humidity sensor manufacturers supplying compatible per-hive hardware.
- Connectivity partners (LoRaWAN, cellular IoT, and gateway providers) enabling remote data transmission from apiaries.
- Beekeeping associations, local clubs, and apiary educators that provide trusted access to small-scale beekeepers.
- Experienced beekeeping advisors who can review anomalous hive trends for the HivePulse Care service.

**Ключові активності**
- Ingest, validate, and store weight, temperature, and humidity measurements separately for every connected hive.
- Develop seasonal baselines and anomaly alerts that distinguish normal changes from trends requiring a hive inspection.
- Onboard customers by guiding sensor installation, hive labeling, connectivity setup, and first-dashboard use within 30 minutes.
- Curate compatible monitoring kits and coordinate scheduled expert review for customers using marketplace and Care offerings.

**Ключові ресурси**
- Hive-level monitoring platform with dashboards, alert rules, historical trend views, and per-hive data records.
- Sensor-integration layer supporting hive scales and temperature/humidity devices from approved hardware partners.
- Seasonal measurement dataset and anomaly-detection logic for interpreting changes across individual hives.
- Beekeeping domain expertise and advisor network for actionable HivePulse Care recommendations.

**Ціннісні пропозиції**
- A separate, understandable dashboard for each hive’s weight, temperature, and humidity, addressing the lack of continuous hive-level visibility.
- Alerts for unusual weight or environmental changes help beekeepers prioritize the hive that needs inspection, reducing unnecessary openings and disturbance.
- Historical trends and seasonal baselines make normal patterns and abnormal deviations easier to recognize despite irregular manual records.
- Optional expert-guided review explains why a colony may need attention, supporting timely, evidence-based decisions about hidden colony issues.

**Відносини з клієнтами**
- Self-service onboarding with installation guidance and an in-app first-hive setup flow designed to deliver initial value in about 30 minutes.
- Automated per-hive alerts, weekly summaries, and historical dashboards throughout the beekeeping season.
- Responsive technical support for sensor connectivity, calibration, and replacement-part issues.
- Scheduled expert review and escalation recommendations for HivePulse Care customers, with a first reviewed status report within 7 days after installation.

**Канали**
- Direct website and mobile app for subscription signup, dashboard access, and alert delivery.
- Beekeeping associations, local clubs, field days, and educational workshops targeting small apiaries.
- Specialist beekeeping equipment retailers and the curated HivePulse Market for compatible devices and installation services.
- Referral partnerships with experienced beekeepers and advisors who demonstrate per-hive monitoring benefits.

**Сегменти клієнтів**
- Small-scale beekeepers managing 5–50 hives who need separate remote visibility into each colony’s weight, temperature, and humidity.
- Small-scale beekeepers who cannot open every hive frequently because of time, weather, or distance from the apiary.
- Small-scale beekeepers with 10–50 hives who want expert-guided prioritization when individual hive measurements become unusual.

**Структура витрат**
- Recurring SaaS costs for cloud data ingestion, time-series storage, dashboards, notifications, and anomaly-detection development supporting subscription MRR.
- Hardware integration, testing, supplier management, marketplace operations, and payment processing tied to transaction-fee GMV.
- Customer acquisition through beekeeping associations, retailers, demonstrations, onboarding, and technical support.
- Advisor compensation and service operations for scheduled monitoring reviews under the retainer-plus-SaaS Care offering.

**Потоки доходів**
- Monthly or annual per-connected-hive subscription for dashboards, historical data, seasonal baselines, and anomaly alerts; key metric: MRR.
- Commission on sales of compatible hive scales, temperature/humidity sensors, connectivity devices, replacement parts, and optional installation services; key metric: GMV.
- Annual or seasonal HivePulse Care retainer bundling sensor setup, SaaS access, and scheduled expert review; key metric: ACV.

## Блок: Архітектура моделі

**Епіцентр:** multiple_epicenter

The canvas shifts together around Key Resources, Value Propositions, and Revenue Streams. Its differentiated per-hive monitoring platform, sensor-integration layer, seasonal dataset, and anomaly-detection logic in key_resources enable the dashboard, alerts, historical baselines, and optional expert interpretation in value_propositions. These capabilities are paired with three coordinated monetization approaches—per-hive subscriptions, equipment-sale commissions, and a Care retainer—rather than representing a change in only one canvas block.

**Патерн:** open_business_model / outside_in

The canvas systematically depends on external contributors to create and deliver the offer: sensor manufacturers provide compatible hardware, connectivity providers transmit field data, associations and retailers provide access and distribution, and independent beekeeping advisors contribute expert review. The key_activities explicitly include hardware curation and coordinating expert review, while the sensor-integration layer and advisor network are core resources. This is outside-in open innovation because partner technologies, domain knowledge, and channels are brought into HivePulse's internal monitoring service; the canvas does not show licensing its own platform or data assets outward.

## Блок: Альтернативи (What-If)

### Focused SaaS · Sensor-Agnostic Hive Monitoring
Concentrate HivePulse on a simple, scalable per-hive SaaS offer for small apiaries, reducing operationally complex marketplace and advisor services. This remains an outside-in open business model because it continues to rely on hardware and connectivity partners, but shifts the epicenter toward the core monitoring data

- **eliminate** (revenue_streams): Annual or seasonal HivePulse Care retainer bundling sensor setup, SaaS access, and scheduled expert review; key metric: ACV. — Removing the managed-service revenue line avoids building a labor-intensive advisor operation and keeps the business focused on scalable software.
- **reduce** (key_activities): Curate compatible monitoring kits and coordinate scheduled expert review for customers using marketplace and Care offerings. -> Maintain a short certified-compatibility list for partner hardware, with referrals rather than marketplace operations or scheduled expert-review coordination. — A lightweight compatibility program lowers supplier, inventory, and service-coordination complexity while preserving customer confidence in device selection.
- **raise** (revenue_streams): Monthly or annual per-connected-hive subscription for dashboards, historical data, seasonal baselines, and anomaly alerts; key metric: MRR. -> Tiered monthly or annual per-connected-hive subscriptions for dashboards, historical data, seasonal baselines, anomaly alerts, and multi-apiary management; key metric: MRR. — Tiered SaaS plans strengthen recurring revenue and let customers expand from basic monitoring to more advanced management as their apiaries grow.
- **create** (value_propositions): A sensor-agnostic certified-device setup that lets beekeepers connect approved third-party hardware to one per-hive monitoring dashboard. — Reducing hardware dependence makes adoption easier for beekeepers who already own compatible scales or environmental sensors.

Очікуваний ефект: Lower service and marketplace operating costs, clearer product positioning, and stronger MRR potential, at the cost of foregoing Care-retainer revenue and some customers who need expert interpretation.

### Apiary Benchmark Network · Cooperative Intelligence
Turn HivePulse from an outside-in open business model into a multi-sided data-network model: participating beekeepers contribute consented, anonymized hive data and receive local, seasonal benchmarking insights. The strategic bet is that network intelligence becomes more valuable than standalone device dashboards.

- **eliminate** (revenue_streams): Commission on sales of compatible hive scales, temperature/humidity sensors, connectivity devices, replacement parts, and optional installation services; key metric: GMV. — Eliminating marketplace commission avoids channel conflict and directs investment toward the data network rather than transactional equipment sales.
- **reduce** (cost_structure): Hardware integration, testing, supplier management, marketplace operations, and payment processing tied to transaction-fee GMV. -> Hardware integration and certification costs for a limited set of interoperable sensor partners, without marketplace operations or transaction-payment processing. — The model needs reliable data interoperability, but not the cost base of operating a hardware marketplace.
- **raise** (key_resources): Seasonal measurement dataset and anomaly-detection logic for interpreting changes across individual hives. -> A consented, anonymized multi-apiary seasonal measurement dataset with local benchmarking, anomaly-detection logic, and privacy controls for interpreting individual hives against comparable cohorts. — A larger and privacy-governed cross-apiary dataset is the strategic asset that enables differentiated benchmark insights.
- **create** (customer_segments): Participating small-scale beekeepers who opt in to anonymized regional benchmarking in exchange for comparative colony-performance insights. — This creates the data-contributor side of the multi-sided model and makes explicit who supplies the network's intelligence.
- **create** (value_propositions): Privacy-preserving regional and seasonal benchmarks that show whether each hive's weight, temperature, and humidity trends differ materially from comparable local colonies. — Comparative context helps beekeepers interpret whether a signal is hive-specific or broadly caused by weather and seasonal conditions.

Очікуваний ефект: A stronger data moat and more actionable interpretation as participation grows, balanced against privacy obligations, cold-start challenges, and the need to earn opt-in trust.

### HivePulse Care Pro · Managed Seasonal Assurance
Reposition HivePulse as a premium managed seasonal-assurance service for 10–50-hive operators who value expert action recommendations over self-service analytics. This retains the outside-in open-business-model pattern, but increases reliance on the advisor network and makes the managed-service value proposition the ep

- **eliminate** (revenue_streams): Monthly or annual per-connected-hive subscription for dashboards, historical data, seasonal baselines, and anomaly alerts; key metric: MRR. — Removing the standalone subscription prevents the offer from competing on low-touch dashboard access and concentrates commercial focus on managed outcomes.
- **reduce** (customer_relationships): Self-service onboarding with installation guidance and an in-app first-hive setup flow designed to deliver initial value in about 30 minutes. -> Assisted installation preparation with a concise customer setup checklist before scheduled remote or partner-led onboarding. — The premium model needs less investment in fully self-service activation and more attention to reliable managed onboarding.
- **raise** (customer_relationships): Scheduled expert review and escalation recommendations for HivePulse Care customers, with a first reviewed status report within 7 days after installation. -> Proactive expert review, prioritized inspection plans, and time-bound escalation recommendations for HivePulse Care customers, with a first reviewed status report within 48 hours after installation. — Faster, more proactive expert engagement is the principal reason customers would pay a premium seasonal retainer.
- **raise** (revenue_streams): Annual or seasonal HivePulse Care retainer bundling sensor setup, SaaS access, and scheduled expert review; key metric: ACV. -> Premium annual or seasonal HivePulse Care retainer bundling assisted setup, SaaS access, proactive expert review, prioritized inspection plans, and time-bound escalation guidance; key metric: ACV. — A richer managed service supports higher ACV and aligns monetization with the differentiated human-guided outcome.
- **create** (value_propositions): A seasonal hive-risk action plan that translates each significant measurement anomaly into a recommended inspection priority, likely cause, and follow-up checklist. — Action plans convert sensor readings into a concrete operational service, reducing customer uncertainty about what to do next.

Очікуваний ефект: Higher ACV and stronger retention among serious small-scale operators, with lower scalability and increased advisor-capacity, quality-control, and service-delivery costs.

## Блок: Гіпотези

- **[desirability / q1]** Among 30 small-scale beekeepers managing 5–50 hives, at least 18 (60%) will identify per-hive alerts for abnormal weight, temperature, or humidity as a reason to inspect a specific hive at least once during a 6-week pilot; the hypothesis is false if fewer than 18 do so.
- **[viability / q1]** At least 12 of 20 pilot beekeepers (60%) will agree to pay at least €4 per connected hive per month for dashboards, historical trends, and anomaly alerts after a 6-week trial; the hypothesis is false if fewer than 12 accept that price.
- **[feasibility / q1]** For at least 90% of 100 monitored hives, the platform can ingest separate weight, temperature, and humidity readings at least every 60 minutes with at least 95% data completeness over a 30-day field pilot; the hypothesis is false if either threshold is missed.
- **[feasibility / q1]** In a 30-day pilot, anomaly rules and seasonal-baseline logic will generate no more than 2 false inspection-priority alerts per hive per month while detecting at least 80% of beekeeper-confirmed major weight-change events; the hypothesis is false if either performance threshold is not met.
- **[desirability / q2]** At least 75% of pilot beekeepers who receive a per-hive weekly summary will continue to view their dashboard in week 6 after completing first-hive setup, indicating that ongoing individual-hive visibility remains useful beyond installation; the hypothesis is false if retention is below 75%.
- **[viability / q3]** At least 20% of 25 small-scale beekeepers with 10–50 hives will state that they would pay an additional €150 per season for scheduled expert review and escalation recommendations; the hypothesis is false if fewer than 5 express this willingness to pay.
- **[feasibility / q4]** At least 85% of 20 new customers will complete hive labeling, connectivity setup, and first-dashboard access within 30 minutes using guided onboarding; the hypothesis is false if fewer than 17 customers complete the flow in that time.

## Блок: Сценарій використання

**Персона:** Olena — Small-scale beekeeper managing a 12-hive family apiary
Біль: Olena lacks continuous, hive-level visibility into changes in weight, temperature, and humidity, so hidden colony issues can be discovered too late.

**Часова шкала:**
- [context] After several rainy days, Olena can visit her 12-hive apiary only on weekends and worries that one colony may be losing stores or accumulating excess moisture without visible signs.
- [goal] She wants to identify which individual hive, if any, requires an inspection before opening healthy colonies unnecessarily.
- [action] Olena checks HivePulse, where each hive has a separate dashboard for weight, temperature, and humidity; an alert highlights Hive 7 for an unusual overnight weight drop and rising humidity compared with its seasonal baseline.
- [result] Instead of relying on a general apiary impression, Olena receives a clear per-hive alert and trend history that prioritizes Hive 7 for inspection while indicating that the other hives remain within expected ranges.
- [impact] Olena visits and inspects only Hive 7, finds a ventilation issue early, corrects it, and avoids disturbing the remaining colonies while gaining confidence that she can manage the apiary remotely between visits.

**До:** €0/month — Monitoring subscription MRR from Olena's apiary
**Після:** €48/month — Monitoring subscription MRR from 12 connected hives at €4 per hive per month

## Блок: Презентація (Pitch)

**Для інвестора:**
- *hook* — **Every hive can signal trouble before it becomes visible**: HivePulse turns continuous weight, temperature, and humidity readings into a clear answer: which hive needs attention now?
- *problem* — **Small apiaries lack visibility where it matters: each hive**: Beekeepers lack continuous hive-level visibility; manual inspections are time-consuming and disturbing, while missed changes can signal swarming, food shortages, excess moisture, or abnormal colony activity. Conditions vary by hive, and infrequent records make meaningful trends hard to recognize.
- *solution* — **Per-hive alerts turn sensor data into inspection priorities**: HivePulse provides a separate dashboard for every hive, anomaly alerts for unusual weight or environmental changes, and seasonal trend baselines. Optional expert-guided review adds practical context for beekeepers who need help interpreting a signal.
- *traction* — **A 12-hive apiary can create €48 in monthly recurring revenue**: Potential: at €4 per connected hive per month, Olena's 12-hive apiary represents €48 MRR; 100 similarly sized connected apiaries would represent €4,800 MRR. The scalable core metric is MRR from tiered per-hive monitoring subscriptions.
- *ask* — **Seeking €300k to prove reliable, paid per-hive monitoring**: Funds will de-risk the highest-risk pilot milestones: connect 100 hives with 95% data completeness, validate alert accuracy, and test whether at least 60% of 20 pilot users will pay €4+ per hive per month after six weeks. Capital supports hardware integrations, field operations, onboarding, and product development.

**Для клієнта:**
- *opening* — **After rainy days, you should not have to guess which hive is at risk**: Like Olena managing 12 hives, you may only reach your apiary on weekends while moisture or changing stores develop unnoticed between visits.
- *empathy* — **You cannot open every hive every day—and you should not have to**: “I need to know which individual hive needs attention before the problem becomes visible.” You may feel uncertain when a hive goes unchecked and responsible for every colony through changing weather.
- *transformation* — **Inspect the one hive that needs you, not every hive**: HivePulse shows separate weight, temperature, and humidity trends for every hive and flags unusual changes. Instead of a general apiary impression, you can prioritize Hive 7-like alerts, correct issues earlier, and leave healthy colonies undisturbed.
- *social_proof* — **Example: 12 connected hives, one prioritized inspection**: Example: after an overnight weight drop and rising humidity alert, a 12-hive beekeeper inspects only the flagged hive, finds a ventilation issue, and avoids opening the other 11. At €4 per hive per month, that apiary plan is €48/month.
- *invitation* — **Connect your first hive and see its story in 30 minutes**: Join the HivePulse pilot to set up hive labeling, connectivity, and your first dashboard. Get clear per-hive trends and alerts that help you decide where your next inspection matters most.
