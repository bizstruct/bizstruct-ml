## Рубрика оцінювання

Шкала 1–5 по кожному критерію. Оцінюється **проєкт цілком**, не окремий блок.

### K5. Придатність гіпотез до перевірки

- **1** — гіпотези без критерію перевірки («клієнтам потрібен наш продукт»)
- **3** — конкретні, але спосіб перевірки неочевидний або результат неоднозначний
- **5** — кожна гіпотеза містить перевірюване твердження, зрозумілий експеримент, покрито всі три категорії ризику

### K4. Економічна правдоподібність

Чи тримається бізнес-логіка. Дивитись: чи є хтось, хто платить; чи співвідносяться витрати й надходження; чи відповідає канал збуту сегменту; чи не суперечить обраний патерн решті моделі.

- **1** — модель не працює економічно
- **3** — життєздатна, але є непроговорене сумнівне припущення
- **5** — економіка узгоджена, ризиковані припущення винесені в гіпотези

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

### K1. Узгодженість між артефактами

Чи описують усі артефакти одну й ту саму бізнес-модель. Дивитись: сегмент у карті емпатії ↔ персона в сценарії ↔ customer_segments у канвасі; обрана монетизація ↔ revenue_streams; болі клієнта ↔ ціннісні пропозиції; ключові ресурси ↔ структура витрат; гіпотези ↔ припущення канвасу.

- **1** — артефакти описують фактично різні бізнеси
- **3** — загальна лінія витримана, є одна-дві помітні розбіжності в деталях
- **5** — наскрізна узгодженість, кожен артефакт виводиться з попередніх

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

Інструмент допомагає невеликим магазинам окремо планувати викладку товарів на полицях з урахуванням фактичного руху покупців.

## Блок: Карта емпатії

**Каже**
- As the owner-manager of a small grocery store, I need to know which shelves shoppers actually pass and where they stop.
- I rearrange products based on intuition, but I cannot easily tell whether a new layout improves customer flow.
- I want popular and high-margin items to be visible without making the aisles confusing.
- I do not have time to create a separate shelf plan for every section by hand.

**Думає**
- If I understood real customer movement, I could place key products in locations that receive more attention.
- Some shelves may be underperforming simply because customers rarely reach or notice them.
- Changing the layout can disrupt regular customers, so I need evidence before moving products.
- A practical plan must fit my store’s actual aisle widths, fixtures, and daily operations.

**Робить**
- The owner-manager walks the store and informally watches how shoppers enter, move through aisles, and queue at checkout.
- The owner-manager periodically moves products, promotions, and seasonal displays between shelves.
- The owner-manager relies on sales reports and staff comments to judge whether a shelf arrangement is working.
- The owner-manager tries to keep frequently requested products stocked while deciding where to place complementary items.

**Відчуває**
- The owner-manager feels uncertain when making shelf-layout decisions without clear evidence of shopper behavior.
- The owner-manager feels frustrated when effort spent rearranging displays does not produce an obvious improvement.
- The owner-manager feels pressured to use limited selling space effectively.
- The owner-manager feels cautious about changes that could inconvenience regular shoppers or staff.

**Болі**
- The owner-manager lacks a clear view of actual customer traffic patterns around individual shelves and zones.
- The owner-manager cannot reliably connect a product’s shelf location with how many shoppers see or approach it.
- The owner-manager spends time making manual layout changes that may be based on assumptions rather than observed movement.
- The owner-manager struggles to plan shelf layouts independently for different store areas with different customer traffic.
- The owner-manager risks leaving valuable shelf space underused while crowded or poorly arranged areas reduce browsing comfort.

**Вигоди**
- The owner-manager wants a clear, practical picture of how shoppers move through the store and interact with shelf areas.
- The owner-manager wants separate shelf-layout recommendations that reflect traffic in each part of the store.
- The owner-manager wants to make faster merchandising decisions with confidence rather than relying mainly on intuition.
- The owner-manager wants to place priority, promotional, and complementary products where customers are more likely to encounter them.
- The owner-manager wants a store layout that improves product visibility while keeping navigation simple for shoppers.

## Блок: Варіанти бізнес-моделі

### Subscription · ShelfFlow Planner
- Аудиторія: Owner-managers of small grocery and convenience stores who personally manage merchandising and shelf changes
- Ціннісна пропозиція: Turn observed shopper movement into zone-specific shelf plans that improve product visibility without disrupting store navigation.
- Опис: Monthly software subscriptions provide traffic heatmaps, shelf-zone recommendations, and before-versus-after layout comparisons for small store owner-managers. It directly addresses pain 1 (no clear view of traffic around shelves), pain 4 (difficulty planning each area independently), and gain 2 (traffic-specific recommendations by store area). A self-serve plan fits owners who need faster, evidence-based merchandising decisions without manually creating every planogram.
- Монетизація: subscription
- Ключова метрика: MRR
- Час до цінності: 45 minutes to first store traffic map and shelf-zone recommendation
- Оцінка: 88 — High fit because recurring traffic insights and iterative shelf changes create an ongoing reason to subscribe, directly serving the core uncertainty around shopper movement and layout decisions. Adoption may be limited by the effort or hardware needed to capture reliable movement data in small stores.

### Transaction Fee · ShelfFlow Layout Marketplace
- Аудиторія: Owner-managers of small grocery and convenience stores seeking occasional, store-specific shelf-layout redesigns
- Ціннісна пропозиція: Buy a verified, traffic-informed shelf-layout plan only when a store section needs to be changed.
- Опис: The platform charges a fee or commission on each purchased layout analysis, redesign package, or implementation booking from merchandising specialists. It addresses pain 3 (time spent on assumption-led manual changes), pain 5 (underused shelf space and browsing friction), and gain 3 (faster decisions with confidence) by letting owners obtain targeted help for a promotion, seasonal reset, or underperforming zone. This suits stores with episodic needs, but transaction revenue is less predictable than recurring software revenue.
- Монетизація: transaction_fee
- Ключова метрика: GMV
- Час до цінності: 3 business days to a purchased zone-layout plan
- Оцінка: 65 — Moderate fit because small stores may prefer paying only for major resets rather than committing to software. The model is weaker because it requires enough qualified merchandising providers and may not capture the continuous traffic-learning value central to the idea.

### Retainer Plus SaaS · ShelfFlow Managed Optimization
- Аудиторія: Owner-managers of multi-section independent grocery stores who need ongoing merchandising guidance but lack time for hands-on analysis
- Ціннісна пропозиція: Get continuous shopper-flow analytics plus a merchandising expert who turns them into practical, staff-ready shelf changes.
- Опис: Customers pay an annual SaaS license plus a monthly or quarterly optimization retainer for data review, tailored shelf plans, and implementation support. The model directly addresses pain 2 (inability to link shelf position to shopper exposure), pain 3 (manual changes based on assumptions), and gain 4 (placing priority and complementary products where shoppers encounter them). It is especially suited to owners who want evidence before making changes that could inconvenience regular customers, as reflected in pain 5 and gain 5.
- Монетизація: retainer_plus_saas
- Ключова метрика: ACV
- Час до цінності: 7 days to first traffic review and staff-ready shelf action plan
- Оцінка: 78 — Strong fit for time-constrained owner-managers because expert support converts movement data into operationally realistic changes. It scores below pure subscription because the service layer raises delivery cost and may exceed the budgets of the smallest stores.

## Блок: Бізнес-модель канвас

**Ключові партнери**
- Low-cost, privacy-conscious footfall sensing providers (ceiling sensors or edge-camera systems) that capture anonymous movement by store zone.
- POS and inventory software vendors that provide product, category, promotion, and sales data for shelf-performance comparisons.
- Independent merchandising specialists who can deliver paid zone redesigns and implementation support through the layout marketplace or managed retainer.
- Independent grocery and convenience-store associations, wholesalers, and franchise networks that can introduce the product to owner-managers.

**Ключові активності**
- Convert anonymous shopper movement into store-zone heatmaps, pass-by counts, dwell time, and congestion signals around individual shelf areas.
- Generate separate, operationally realistic shelf-layout recommendations for each store section, accounting for aisle widths, fixtures, and customer navigation.
- Compare before-versus-after traffic exposure and sales-related signals after a shelf or promotional-display change.
- Onboard stores, map floor plans and shelf zones, and coordinate merchandising experts for purchased redesign packages and managed optimization reviews.

**Ключові ресурси**
- Traffic-analytics and recommendation engine that links shopper movement patterns to shelf zones and layout alternatives.
- Store floor-plan, fixture, shelf-zone, product-category, promotion, and historical movement data.
- Integrations and deployment capability for footfall sensors, POS systems, and inventory data sources.
- Merchandising expertise and a vetted specialist network for expert-reviewed layouts and staff-ready action plans.

**Ціннісні пропозиції**
- Show a practical picture of actual shopper routes, pass-by traffic, and stopping behavior around shelf zones, addressing the lack of visibility into traffic patterns.
- Create separate traffic-informed shelf plans for each store area, so owners do not have to manually plan every section and can account for different traffic levels.
- Recommend placements for priority, promotional, and complementary products in zones shoppers are more likely to encounter, improving visibility while preserving straightforward navigation.
- Provide before-versus-after layout comparisons so owners can make evidence-based changes instead of relying on intuition or risking disruptive rearrangements for regular customers.

**Відносини з клієнтами**
- Self-serve subscription onboarding: guide an owner-manager through floor-plan upload, shelf-zone setup, and first traffic map within the stated 45-minute time to value.
- In-product recommendation workflow with actionable zone-level changes, saved layout versions, and before-versus-after comparisons for recurring merchandising decisions.
- On-demand expert relationship for a purchased redesign package, targeting delivery of a zone-layout plan within 3 business days.
- Managed optimization relationship for eligible stores: recurring traffic review, tailored shelf plans, and staff-ready actions, with a first review in 7 days.

**Канали**
- Direct digital acquisition through a product website, interactive demo heatmaps, and a self-serve store-layout onboarding flow.
- Outbound sales to owner-managers of independent grocery and convenience stores, focused on stores where owners make shelf decisions themselves.
- Referrals and co-marketing through POS vendors, footfall-sensor providers, wholesalers, and independent retailer associations.
- Merchandising specialists use the marketplace channel to bring clients needing seasonal resets, promotions, or underperforming-zone redesigns.

**Сегменти клієнтів**
- Owner-managers of small independent grocery stores who personally monitor customer movement, manage merchandising, and periodically move products and displays.
- Owner-managers of small convenience stores who need to use limited selling space effectively and make shelf changes without extensive manual planning.
- Owner-managers of multi-section independent grocery stores who lack time for hands-on analysis and need ongoing merchandising guidance.

**Структура витрат**
- Software development, cloud processing, data storage, and ongoing maintenance of traffic heatmaps, shelf-zone recommendations, and layout comparison features for the subscription product.
- Footfall-sensor integration, deployment support, floor-plan mapping, and privacy/security controls needed to produce reliable movement data.
- Merchandising-specialist fees, quality assurance, marketplace operations, and payment processing for transaction-based redesign packages.
- Account management and expert delivery time for recurring traffic reviews, tailored shelf plans, and implementation support under the retainer-plus-SaaS offer.

**Потоки доходів**
- Monthly SaaS subscriptions for traffic heatmaps, shelf-zone recommendations, and before-versus-after layout comparisons; tracked by MRR.
- Transaction fees or commissions on each purchased traffic-informed layout analysis, redesign package, or merchandising-specialist implementation booking; tracked by GMV.
- Annual SaaS licenses combined with monthly or quarterly optimization retainers for ongoing expert review, staff-ready shelf plans, and implementation support; tracked by ACV.

## Блок: Архітектура моделі

**Епіцентр:** multiple_epicenter

The canvas combines a resource-driven core with an offer-driven redesign. Its key_resources and key_activities center on a traffic-analytics and recommendation engine, anonymized footfall sensing, POS integrations, and a merchandising-specialist network; these capabilities enable the differentiated value_propositions of zone-specific shelf plans and measurable before-versus-after comparisons. Customer relationships, partner deployment, and the recurring SaaS, transaction, and managed-service offers are all structured around converting these resources into operational merchandising actions.

**Патерн:** multi_sided_platform

The canvas includes a platform-like connection between distinct interdependent groups: store owner-managers needing layout redesigns and independent merchandising specialists who supply expert-reviewed plans and implementation support. The key_partners identify the specialist network, channels state that specialists bring clients through the marketplace, customer_relationships offer on-demand purchased redesign packages, and revenue_streams collect transaction fees or commissions on those bookings. SaaS subscriptions and managed retainers coexist, but the marketplace linkage is the clearest canonical pattern expressed in the canvas.

## Блок: Альтернативи (What-If)

### Lean Self-Serve Shelf Planner
Make the core offer a single-sided, self-serve SaaS business for small stores, rather than the current multi-sided platform that also coordinates merchandising specialists. The bet is that rapid, low-friction planning from simple store inputs will outperform sensor-heavy deployment and service complexity.

- **eliminate** (key_partners): Independent merchandising specialists who can deliver paid zone redesigns and implementation support through the layout marketplace or managed retainer. — Removes dependence on a two-sided specialist supply base and focuses the model on software-led decisions.
- **reduce** (cost_structure): Footfall-sensor integration, deployment support, floor-plan mapping, and privacy/security controls needed to produce reliable movement data. -> Lightweight floor-plan setup, optional existing-sensor connections, and baseline privacy controls for stores that want movement data. — Cuts deployment cost and onboarding friction by making dedicated sensing optional rather than a prerequisite.
- **raise** (customer_relationships): Self-serve subscription onboarding: guide an owner-manager through floor-plan upload, shelf-zone setup, and first traffic map within the stated 45-minute time to value. -> Highly guided self-serve subscription onboarding with mobile floor-plan capture, shelf-zone templates, and a first actionable layout recommendation within 15 minutes. — A much faster first result is essential when the owner-manager must adopt and use the product without expert support.
- **create** (value_propositions): Generate practical shelf-layout scenarios from a store photo or simple floor-plan sketch, using owner-entered traffic observations when sensor data is unavailable. — Creates an accessible entry offer for stores unwilling or unable to install footfall hardware.
- **create** (revenue_streams): Tiered self-serve SaaS subscriptions priced by number of store zones and layout scenarios, with an optional add-on for live sensor data. — Aligns recurring revenue with a lean product while preserving an upgrade path for higher-fidelity analytics.

Очікуваний ефект: Lower customer acquisition and onboarding barriers, faster activation, and more scalable recurring revenue, offset by less precise movement insight and the loss of service-led revenue.

### Premium Managed Merchandising Partner
Concentrate on a high-trust managed optimization service for larger independent stores, using the existing analytics and expert network to sell measurable merchandising outcomes rather than standalone software or one-off marketplace jobs. This retains the multi-sided platform structure but makes expert-delivered value,

- **eliminate** (revenue_streams): Transaction fees or commissions on each purchased traffic-informed layout analysis, redesign package, or merchandising-specialist implementation booking; tracked by GMV. — Eliminates episodic marketplace monetization that distracts from predictable, outcome-oriented managed contracts.
- **reduce** (customer_segments): Owner-managers of small convenience stores who need to use limited selling space effectively and make shelf changes without extensive manual planning. -> A limited pilot segment of convenience-store owner-managers with multiple locations and sufficient budget for recurring optimization. — Narrows the addressable segment to customers able to fund recurring expert involvement and implement recommendations.
- **raise** (customer_relationships): Managed optimization relationship for eligible stores: recurring traffic review, tailored shelf plans, and staff-ready actions, with a first review in 7 days. -> Premium managed optimization partnership with weekly traffic review, expert-approved zone plans, staff implementation checklists, and quarterly performance reviews, with a first review in 48 hours. — Raises service intensity and response standards to make the offer operationally indispensable.
- **raise** (value_propositions): Provide before-versus-after layout comparisons so owners can make evidence-based changes instead of relying on intuition or risking disruptive rearrangements for regular customers. -> Provide expert-validated before-versus-after performance reviews that connect layout changes to traffic exposure, category sales signals, implementation quality, and next actions. — Strengthens proof of value from a dashboard comparison into a managed decision and accountability system.
- **create** (revenue_streams): Outcome-linked annual optimization contracts combining SaaS access, expert review, implementation support, and performance bonuses tied to agreed category or zone improvement targets. — Creates premium recurring contracts aligned with demonstrated operational and commercial outcomes.

Очікуваний ефект: Higher ACV, retention, and customer trust for a narrower segment, with lower service scalability and greater reliance on expert-delivery quality.

### Retail Traffic Benchmark Cooperative
Shift the current marketplace-oriented multi-sided platform toward an open-business-model data cooperative: participating retailers receive free or low-cost benchmarking tools in exchange for contributing privacy-safe, aggregated movement and layout data. The bet is that a shared benchmark network becomes the defensib

- **eliminate** (customer_relationships): On-demand expert relationship for a purchased redesign package, targeting delivery of a zone-layout plan within 3 business days. — Removes the bespoke on-demand service path so participation and learning can scale through standardized network tools.
- **reduce** (revenue_streams): Monthly SaaS subscriptions for traffic heatmaps, shelf-zone recommendations, and before-versus-after layout comparisons; tracked by MRR. -> Low-cost membership subscriptions for store-specific heatmaps and layout comparisons, with core benchmarking access included for participating data contributors. — Reduces the paywall on the core product to accelerate retailer participation and data-network coverage.
- **raise** (key_resources): Store floor-plan, fixture, shelf-zone, product-category, promotion, and historical movement data. -> A large, consent-based and privacy-preserving cross-store dataset of floor plans, fixture types, shelf zones, product categories, promotions, and historical movement outcomes. — Raises the strategic importance, scale, and governance quality of aggregated data as the cooperative's core asset.
- **create** (value_propositions): Anonymous peer benchmarks that show how a store's zone traffic, dwell time, congestion, and promotion exposure compare with similar store formats, sizes, and layouts. — Creates a network-derived value proposition unavailable from a store's isolated data alone.
- **create** (key_partners): Privacy-governance, retailer-association, and academic research partners that set aggregation standards and validate cooperative benchmark methodology. — Adds trusted governance partners needed to secure retailer participation and make shared benchmarks credible.

Очікуваний ефект: Potentially faster network growth, stronger data defensibility, and new future monetization options such as benchmark reports or supplier insights, balanced against harder privacy governance and lower near-term subscription revenue.

## Блок: Гіпотези

- **[desirability / q1]** At least 60% of interviewed owner-managers of independent grocery and convenience stores will identify zone-level shopper traffic data as a top-three input for their next shelf-layout decision after reviewing a sample traffic heatmap and shelf recommendation.
- **[viability / q1]** At least 40% of qualified small-store owner-managers who receive a personalized demonstration will start a paid monthly subscription at a price of at least $99 per store per month for traffic heatmaps, zone-specific shelf recommendations, and layout comparisons.
- **[feasibility / q1]** A pilot deployment using privacy-conscious footfall sensing can produce zone-level pass-by counts with at least 85% agreement against manual observation across 20 one-hour observation periods in a small store.
- **[desirability / q1]** In a 12-week pilot, at least 50% of stores that implement one recommended shelf-zone change will record a minimum 10% increase in pass-by exposure or dwell time for the changed zone versus the four-week pre-change baseline, without increasing reported aisle-congestion incidents.
- **[feasibility / q2]** At least 70% of owner-managers completing initial store setup can upload a floor plan, define five shelf zones, and view their first traffic map within 45 minutes without live onboarding assistance.
- **[viability / q3]** At least 25% of stores offered an on-demand expert redesign package will purchase one at a price of at least $300 after receiving their first traffic analysis.

## Блок: Сценарій використання

**Персона:** Olena — Owner-manager of a small independent grocery store
Біль: Olena lacks a clear view of actual customer traffic patterns around individual shelves and zones.

**Часова шкала:**
- [context] While preparing a weekend promotion, Olena sees customers crowd near the entrance while a high-margin snack shelf at the back receives little attention, but she has no reliable zone-level evidence to guide a move.
- [goal] She wants to place promotional and complementary products where shoppers are likely to encounter them while keeping the store’s narrow aisles easy for regular customers to navigate.
- [action] Olena uploads her floor plan, marks shelf zones, and uses ShelfFlow’s shopper-route heatmap, pass-by counts, dwell-time signals, and zone-specific shelf recommendations to test a new placement for snacks and drinks.
- [result] She receives a practical shelf plan for the entrance and beverage areas that identifies high-exposure zones, flags a potential congestion point, and provides a before-versus-after comparison for the implemented display change.
- [impact] Olena makes the merchandising change with evidence rather than intuition, spends less time debating layouts with staff, and can repeat the same measurement process for future promotions.

**До:** 4 hours per week — Time spent manually observing traffic and planning shelf changes
**Після:** $99 per store per month — Monthly recurring revenue (MRR) from an active ShelfFlow subscription

## Блок: Презентація (Pitch)

**Для інвестора:**
- *hook* — **Small stores still place their best products on intuition**: Owner-managers spend hours watching aisles and moving displays, yet lack evidence of which shelf zones shoppers actually pass, notice, or avoid.
- *problem* — **Valuable shelf space is being managed without zone-level evidence**: Owners lack a clear view of traffic around shelves and cannot reliably connect product location with shopper exposure. They spend time on assumption-led changes, struggle to plan each area separately, and risk underused space, congestion, and confusing layouts.
- *solution* — **ShelfFlow turns shopper movement into shelf actions**: Privacy-conscious traffic maps show routes, pass-by traffic, stops, and congestion by shelf zone; the platform creates separate, operationally realistic plans for each store area. Before-versus-after comparisons help place priority, promotional, and complementary products with evidence while preserving easy navigation.
- *traction* — **A $99 monthly workflow can replace 4 hours of weekly guesswork**: Potential: at $99 per active store per month, 100 subscribed stores would generate $9,900 MRR, while giving each owner a repeatable alternative to the 4 hours per week spent manually observing traffic and planning shelf changes. Example pilot target: 50% of stores achieve at least a 10% lift in pass-by exposure or dwell time after one recommended change.
- *ask* — **Seeking $500K to validate paid demand and sensing accuracy**: Fund a 12-month pilot across 20–30 independent stores: validate 85%+ agreement between sensing and manual zone counts, prove 45-minute self-serve setup, and test whether at least 40% of qualified demo recipients convert at $99+ per store per month. Funds support sensor/POS integrations, product onboarding, privacy controls, and pilot acquisition.

**Для клієнта:**
- *opening* — **Stop guessing why your best shelf gets ignored**: You see crowds near the entrance while a high-margin snack shelf at the back gets little attention. Before moving products for the weekend promotion, get evidence of where shoppers actually go.
- *empathy* — **You know your store—but intuition should not carry every decision**: “I rearrange products based on intuition, but I cannot easily tell whether a new layout improves customer flow.” You feel pressured to use limited selling space well and cautious about changes that inconvenience regular customers or staff.
- *transformation* — **Turn 4 hours of observation into a repeatable shelf decision**: Upload your floor plan, mark shelf zones, and see shopper routes, pass-by counts, dwell signals, and congestion risks. Get a practical plan for each area, test the change, and compare results before deciding what to repeat for the next promotion.
- *social_proof* — **See what a traffic-informed change could reveal**: Example: a small grocery owner moved snacks beside a high-exposure beverage zone after reviewing the heatmap, while avoiding an entrance congestion point. Example pilot benchmark: a recommended zone change aims for at least a 10% increase in pass-by exposure or dwell time without added aisle-congestion incidents.
- *invitation* — **Map your first five shelf zones in 45 minutes**: Start with your floor plan and one upcoming promotion; ShelfFlow guides you from shelf-zone setup to a first traffic map and actionable recommendation. Join the pilot for $99 per store per month.
