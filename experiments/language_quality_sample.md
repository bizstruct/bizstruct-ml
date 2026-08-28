# Quality sample — side-by-side model comparison

Raw generated content only, no scoring. Read `expected_pattern` in dataset.json alongside this to judge fit, not just fluency.

## idea-001

> unbundling / minimal / b2b / сільське господарство

### idea-001 — architecture

**language_comparison__gpt-5.6-terra__uk**

```json
{
  "epicenter": "resource_driven",
  "epicenter_rationale": "Первинним драйвером моделі є розділ ключових ресурсів: платформа HiveWatch, комплект сумісних вагових платформ і датчиків, а також алгоритми аналізу часових рядів та аномалій. Ключові активності з калібрування обладнання, контролю якості даних, їх збирання й автоматичного виявлення відхилень прямо перетворюють цю технологічну основу на цінність для пасічника. Підписка, консультації та канали продажу в Canvas побудовані навколо використання цієї інфраструктури моніторингу по кожному вулику.",
  "pattern": "open_business_model",
  "pattern_subtype": "outside_in",
  "pattern_rationale": "Модель системно залучає зовнішніх партнерів для формування та розвитку основної пропозиції: виробників датчиків і ваг, операторів мереж зв’язку, а також досвідчених бджолярів і ветеринарних консультантів. Зовнішня експертиза використовується для налаштування порогів аномалій, інтерпретації даних і надання консультацій у HiveWatch Care та ProCare, а партнерські магазини й асоціації підтримують поширення рішення. Це відповідає підтипу outside_in, оскільки зовнішні технології та знання інтегруються у внутрішній сервіс, а не ліцензуються назовні."
}
```

**language_comparison__gpt-5.6-terra__en**

```json
{
  "epicenter": "multiple_epicenter",
  "epicenter_rationale": "The canvas combines a resource-driven core—per-hive sensor kits, a cloud data platform, and hive-condition baseline models in key_resources—with an offer-driven layer in value_propositions: continuous individual-hive monitoring, deviation alerts, and historical comparisons. These elements are inseparable in the design: the specialized measurement and interpretation capability enables the differentiated offer, while customer relationships and revenue streams add optional expert support and service bookings around it. The primary innovation therefore shifts both key_resources/key_activities and value_propositions together rather than relying on pricing or a new segment alone.",
  "pattern": "multi_sided_platform",
  "pattern_subtype": null,
  "pattern_rationale": "The canvas includes a primary beekeeper segment and a distinct network of experienced beekeepers, advisors, and local service providers, with HiveCare Exchange taking a transaction fee on completed bookings or sales. Key_partners explicitly include these providers, customer relationships coordinate optional expert reviews, and channels include referrals from advisors; alerts generated for beekeepers can create demand for provider services. Although the subscription SaaS is the main revenue stream, the connected beekeeper-provider interaction makes the multi-sided platform the dominant named pattern present in the broader canvas."
}
```

### idea-001 — hypotheses

**language_comparison__gpt-5.6-terra__uk**

```json
{
  "hypotheses": [
    {
      "id": "H1.1",
      "text": "Щонайменше 60% власників пасік із 5–30 вуликами, які протягом 4 тижнів користуватимуться прототипом панелі й сповіщень по окремих вуликах, повідомлять про готовність замінити щонайменше 1 плановий фізичний огляд на перевірку лише вулика з тривогою; гіпотеза хибна, якщо частка буде нижчою за 60%.",
      "category": "desirability",
      "quadrant": "q1"
    },
    {
      "id": "H1.2",
      "text": "Щонайменше 25% цільових пасічників, яким показано конкретний пакет HiveWatch для 10 вуликів за 1 200 грн на місяць без урахування вартості обладнання, залишать передзамовлення з контактами або внесуть депозит протягом 14 днів; гіпотеза хибна, якщо конверсія буде нижчою за 25%.",
      "category": "viability",
      "quadrant": "q1"
    },
    {
      "id": "H1.3",
      "text": "Після встановлення на 20 вуликах комплект HiveWatch передаватиме щонайменше 95% запланованих годинних вимірювань ваги, температури та вологості протягом 30 днів, а похибка ваги після калібрування не перевищуватиме 1 кг; гіпотеза хибна, якщо хоча б один показник не буде досягнуто.",
      "category": "feasibility",
      "quadrant": "q1"
    },
    {
      "id": "H2.1",
      "text": "Щонайменше 70% пасічників, що підключили мінімум 5 вуликів, відкриватимуть картку конкретного вулика або історію його показників не менше 4 разів протягом перших 30 днів; гіпотеза хибна, якщо частка таких активних користувачів буде нижчою за 70%.",
      "category": "desirability",
      "quadrant": "q2"
    },
    {
      "id": "H3.1",
      "text": "У щонайменше 15% тривожних випадків користувачі HiveWatch Care замовлятимуть платну дистанційну консультацію через платформу протягом 24 годин після сповіщення; гіпотеза хибна, якщо частка замовлень буде нижчою за 15% за перші 100 тривог.",
      "category": "viability",
      "quadrant": "q3"
    },
    {
      "id": "H4.1",
      "text": "Не менше 80% нових клієнтів зможуть самостійно підключити та відкалібрувати один модуль для вулика за 30 хвилин, завершивши передавання першого набору даних без допомоги оператора; гіпотеза хибна, якщо частка успішних самостійних установок буде нижчою за 80%.",
      "category": "feasibility",
      "quadrant": "q4"
    }
  ]
}
```

**language_comparison__gpt-5.6-terra__en**

```json
{
  "hypotheses": [
    {
      "id": "H1.1",
      "text": "At least 60% of interviewed beekeepers managing 5–50 hives will rank separate weight, temperature, and humidity monitoring for each hive among their top 3 operational problems and agree to run a 30-day pilot; fewer than 60% would falsify the core value proposition.",
      "category": "desirability",
      "quadrant": "q1"
    },
    {
      "id": "H1.2",
      "text": "At least 40% of pilot participants with 5–50 hives will commit to paying at least $8 per connected hive per month, excluding hardware, after viewing 30 days of live readings and alerts; a conversion rate below 40% would falsify the per-hive subscription revenue assumption.",
      "category": "viability",
      "quadrant": "q1"
    },
    {
      "id": "H1.3",
      "text": "During a 90-day field pilot, the monitoring system will achieve at least 95% daily data completeness for weight, temperature, and humidity across connected hives and maintain weight-measurement error within ±2 kg versus a calibrated reference scale; failure on either metric would falsify the technical reliability assumption.",
      "category": "feasibility",
      "quadrant": "q1"
    },
    {
      "id": "H1.4",
      "text": "At least 70% of alerts marked as actionable by the system during a 60-day pilot will lead participating beekeepers to inspect, feed, protect, or otherwise change care for the identified hive within 72 hours; a rate below 70% would falsify the assumption that the alerting engine creates actionable hive-specific decisions.",
      "category": "desirability",
      "quadrant": "q1"
    },
    {
      "id": "H2.1",
      "text": "At least 80% of new customers can activate a sensor kit and see valid readings from one hive within 30 minutes using guided self-service onboarding, with no more than one support interaction; a rate below 80% would falsify the planned low-touch onboarding model.",
      "category": "feasibility",
      "quadrant": "q2"
    },
    {
      "id": "H3.1",
      "text": "In each launch region, at least 10 vetted local beekeeping advisors or service providers will accept referrals and complete at least 5 alert-triggered paid service bookings within 6 months; failure to meet both thresholds would falsify the HiveCare Exchange multi-sided-platform assumption.",
      "category": "viability",
      "quadrant": "q3"
    }
  ]
}
```

## idea-026

> long_tail / moderate / b2c / туризм

### idea-026 — architecture

**language_comparison__gpt-5.6-terra__uk**

```json
{
  "epicenter": "offer_driven",
  "epicenter_rationale": "Первинна диференціація міститься у блоці value_propositions: каталог не просто показує локації, а перетворює їх на короткі тематично пов’язані прогулянки з поясненням контексту, послідовністю зупинок, тривалістю і складністю. Блоки key_resources та key_activities — база маршрутів, редакційна методологія, фактчекінг і мапи — прямо побудовані для підтримки цієї пропозиції. Підписка, комісія та SaaS-ліцензії монетизують уже створену цінність, а не є головним джерелом інновації.",
  "pattern": "multi_sided_platform",
  "pattern_subtype": null,
  "pattern_rationale": "Canvas поєднує щонайменше дві взаємозалежні групи: мандрівників, які шукають і бронюють тематичні досвіди, та локальних постачальників пропозиції — гідів, авторів аудіопрогулянок, музеї, культурні простори й туристичні ініціативи. Через ThemeWalk Booking платформа забезпечує бронювання та комісійний потік між мандрівниками й гідами, а через LocalTheme Studio дає організаціям інструмент публікації та аналітики маршрутів. Канали включають як B2C-залучення мандрівників, так і прямі B2B-продажі та партнерські точки доступу, що підтримує двосторонню структуру моделі."
}
```

**language_comparison__gpt-5.6-terra__en**

```json
{
  "epicenter": "resource_driven",
  "epicenter_rationale": "The differentiation is anchored in the Key Resources: a vetted library of niche regional routes, route-authoring SaaS, searchable route data, and an editorial network of local experts. Key Activities are designed to continually research, validate, structure, and publish this hard-to-assemble content asset; the value propositions and several revenue streams are built on top of those resources rather than on an unusual pricing mechanism.",
  "pattern": "multi_sided_platform",
  "pattern_subtype": null,
  "pattern_rationale": "The canvas connects distinct, interdependent groups: educator-curators contribute group-ready routes, travelers discover and use curated routes, and guides, museums, and activity providers supply route-linked paid experiences. The web and mobile platform, partnership distribution channels, authoring tools, and booking commissions create interactions between these groups, while the growing route library strengthens value for both route creators and travelers."
}
```

### idea-026 — hypotheses

**language_comparison__gpt-5.6-terra__uk**

```json
{
  "hypotheses": [
    {
      "id": "H1.1",
      "text": "Щонайменше 40% мандрівників, які планують самостійну поїздку на 1–3 дні та переглянули прототип маршруту, зможуть за 10 хвилин обрати тематичну прогулянку й оцінять готову логіку зупинок, тривалість і локальний контекст на 8 із 10 або вище; результат нижче 40% спростує ключову ціннісну пропозицію каталогу.",
      "category": "desirability",
      "quadrant": "q1"
    },
    {
      "id": "H1.2",
      "text": "Щонайменше 8% нових користувачів, які безкоштовно пройшли один тематичний маршрут, оформлять LocalTheme Pass за ціною 99 грн на місяць або 790 грн на рік протягом 14 днів; конверсія нижче 8% спростує життєздатність підписки як основного B2C-потоку доходу.",
      "category": "viability",
      "quadrant": "q1"
    },
    {
      "id": "H1.3",
      "text": "Щонайменше 30% залучених локальних гідів, музеїв і культурних просторів погодяться опублікувати мінімум один маршрут або платний досвід у пілотному регіоні протягом 30 днів; частка нижче 30% спростує припущення архітектури багатосторонньої платформи про достатнє формування пропозиції.",
      "category": "feasibility",
      "quadrant": "q1"
    },
    {
      "id": "H2.1",
      "text": "Не менше 70% користувачів, які відкрили маршрут на мапі, розпочнуть навігацію або збережуть його для проходження протягом тієї самої сесії; показник нижче 70% спростує припущення, що структурована мапа й параметри маршруту зменшують бар’єр планування короткої поїздки.",
      "category": "desirability",
      "quadrant": "q2"
    },
    {
      "id": "H2.2",
      "text": "Команда з редактора, локального експерта та картографа зможе підготувати, фактчекнути й опублікувати один маршрут із 5–8 зупинок не довше ніж за 24 людино-години та з не більш ніж 5% виявлених користувачами фактичних або навігаційних помилок у перші 30 днів; перевищення будь-якого порога спростує операційну масштабованість моделі курованого каталогу.",
      "category": "feasibility",
      "quadrant": "q2"
    },
    {
      "id": "H3.1",
      "text": "Щонайменше 3% користувачів, які переглянули сторінку платної прогулянки або аудіогіда, завершать бронювання із середнім чеком від 500 грн протягом 30 днів; конверсія нижче 3% спростує доцільність комісійного потоку ThemeWalk Booking у пілотному регіоні.",
      "category": "viability",
      "quadrant": "q3"
    }
  ]
}
```

**language_comparison__gpt-5.6-terra__en**

```json
{
  "hypotheses": [
    {
      "id": "H1.1",
      "text": "At least 40% of 60 history teachers and culturally curious travelers who plan a local outing within the next 90 days will select a route from a clickable prototype within 15 minutes and rate its theme, context, and logistics at 4 or 5 out of 5; the hypothesis is false if fewer than 24 do so.",
      "category": "desirability",
      "quadrant": "q1"
    },
    {
      "id": "H1.2",
      "text": "At least 15% of 100 qualified visitors who complete a route-preview landing-page flow will start a €6/month subscription trial or provide payment authorization for access to vetted map-ready routes; the hypothesis is false if fewer than 15 visitors do so.",
      "category": "viability",
      "quadrant": "q1"
    },
    {
      "id": "H1.3",
      "text": "At least 8 of 20 interviewed schools, museums, or heritage organizations will agree to pay at least €1,200 per year for a route-authoring license after reviewing a group-route prototype and pricing proposal; the hypothesis is false if fewer than 8 organizations agree.",
      "category": "viability",
      "quadrant": "q1"
    },
    {
      "id": "H1.4",
      "text": "Using a standard route-authoring workflow and local-expert review, a two-person editorial team can publish 20 routes with at least 5 stops each in 30 days, while at least 90% of sampled stop hours, locations, and access notes are verified as accurate; the hypothesis is false if either threshold is missed.",
      "category": "feasibility",
      "quadrant": "q1"
    },
    {
      "id": "H2.1",
      "text": "At least 80% of 30 pilot-route users will complete a route without reporting a material sequencing, navigation, or access error, and at least 70% will say the stated duration was within 30 minutes of actual duration; the hypothesis is false if either rate falls below its threshold.",
      "category": "feasibility",
      "quadrant": "q2"
    },
    {
      "id": "H3.1",
      "text": "Within one pilot region, at least 10 of 30 contacted guides, museums, and workshop providers will list a route-linked paid experience with a commission of 15% or less and maintain at least 4 bookable dates per month; the hypothesis is false if fewer than 10 providers meet both conditions.",
      "category": "viability",
      "quadrant": "q3"
    }
  ]
}
```

## idea-070

> free / minimal / b2b2c / спорт

### idea-070 — architecture

**language_comparison__gpt-5.6-terra__uk**

```json
{
  "epicenter": "multiple_epicenter",
  "epicenter_rationale": "Модель одночасно змінює кілька блоків Canvas: у value_propositions поєднано короткі адаптивні тренування з безпечними відеопоясненнями, у key_resources — алгоритм підбору навантаження та експертно перевірену бібліотеку вправ, а в revenue_streams — підписку, комісію за консультації та B2B SaaS-контракти. Ці елементи працюють як єдина конструкція: цифровий базовий продукт формує регулярне користування, тренери додають людську підтримку, а HR-канал створює окремий спосіб придбання доступу. Тому драйвером є не лише пропозиція, ресурс чи монетизація окремо, а їхній взаємопов’язаний редизайн.",
  "pattern": "multi_sided_platform",
  "pattern_subtype": null,
  "pattern_rationale": "Canvas містить щонайменше дві взаємозалежні групи: користувачів-початківців, яким потрібні тренування й перевірка техніки, та онлайн-тренерів, які надають платні відеоконсультації через платформу. Це прямо відображено в key_partners як мережа тренерів, у value_propositions як опційна консультація та в revenue_streams як комісія з кожної оплаченої сесії. Корпоративні HR-партнери також виступають окремим B2B-каналом і платником за доступ команд, хоча підписка на контент лишається додатковим прямим потоком доходу."
}
```

**language_comparison__gpt-5.6-terra__en**

```json
{
  "epicenter": "multiple_epicenter",
  "epicenter_rationale": "The canvas combines customer-driven design and finance-driven access rather than relying on one isolated innovation source. Customer_segments and channels focus tightly on sedentary, inexperienced office workers and add employer wellness distribution, while revenue_streams combine freemium subscriptions, optional coach-session transaction fees, and employer per-employee SaaS licenses with support retainers. These shifts are supported by a differentiated beginner-safe offer, but the coherent redesign is the combination of novice-specific access, delivery, and monetization.",
  "pattern": "free",
  "pattern_subtype": "freemium",
  "pattern_rationale": "The dominant consumer acquisition model is explicitly a freemium app in the App Store and Google Play, and the primary revenue stream is conversion from a free experience to a monthly subscription for adaptive plans, form cues, alternatives, reminders, and tracking. Free users can receive enough value to complete a first beginner workout, while a portion upgrades for ongoing personalization and habit support. Coach fees and employer contracts are supplementary revenue streams, not the main structure that subsidizes the free consumer tier."
}
```

### idea-070 — hypotheses

**language_comparison__gpt-5.6-terra__uk**

```json
{
  "hypotheses": [
    {
      "id": "H1.1",
      "text": "Щонайменше 40% представників цільового сегмента — офісних працівників без тренувального досвіду — після перегляду клікабельного прототипу створять план на 10–20 хвилин і оцінять його релевантність не нижче 8 із 10; гіпотеза хибна, якщо частка буде нижчою за 40%.",
      "category": "desirability",
      "quadrant": "q1"
    },
    {
      "id": "H1.2",
      "text": "Щонайменше 8% користувачів, які завершили безкоштовний 7-денний стартовий маршрут, оформлять місячну підписку за ціною 199 грн протягом 7 днів після завершення пробного періоду; гіпотеза хибна за конверсії нижче 8%.",
      "category": "viability",
      "quadrant": "q1"
    },
    {
      "id": "H1.3",
      "text": "За експертним аудитом 100 автоматично згенерованих стартових планів для різних відповідей анкети щонайменше 95% планів міститимуть лише вправи й прогресію, що відповідають затвердженим правилам безпеки для новачків; гіпотеза хибна, якщо відповідність буде нижчою за 95%.",
      "category": "feasibility",
      "quadrant": "q1"
    },
    {
      "id": "H2.1",
      "text": "Щонайменше 50% нових користувачів, які отримали персоналізований план, виконають не менше 3 тренувань у перші 14 днів; гіпотеза хибна, якщо частка таких користувачів буде нижчою за 50%.",
      "category": "desirability",
      "quadrant": "q2"
    },
    {
      "id": "H3.1",
      "text": "Щонайменше 10% активних користувачів, які в онбордингу зазначили страх травми або невпевненість у техніці, придбають разову відеоконсультацію з тренером протягом перших 30 днів за ціною 400 грн; гіпотеза хибна за конверсії нижче 10%.",
      "category": "viability",
      "quadrant": "q3"
    },
    {
      "id": "H4.1",
      "text": "Щонайменше 95% користувачів на підтримуваних Android та iOS-пристроях зможуть завершити анкету й відкрити перше тренування менш ніж за 15 хвилин без звернення до підтримки; гіпотеза хибна, якщо цей показник буде нижчим за 95%.",
      "category": "feasibility",
      "quadrant": "q4"
    }
  ]
}
```

**language_comparison__gpt-5.6-terra__en**

```json
{
  "hypotheses": [
    {
      "id": "H1.1",
      "text": "Among 100 recruited sedentary adults with no regular exercise habit, at least 60% will complete their first personalized 10–20 minute no-equipment workout within 24 hours of onboarding; a completion rate below 60% falsifies the claim that the core guided workout proposition creates immediate value.",
      "category": "desirability",
      "quadrant": "q1"
    },
    {
      "id": "H1.2",
      "text": "Among new users who complete one free workout in their first 7 days, at least 25% will start a monthly subscription priced at US$7.99–9.99 after seeing adaptive plans, form cues, and progress tracking; a conversion rate below 25% falsifies the primary freemium subscription revenue assumption.",
      "category": "viability",
      "quadrant": "q1"
    },
    {
      "id": "H1.3",
      "text": "In usability testing with 30 absolute beginners, at least 85% will correctly perform at least 8 of 10 prescribed exercise movements after viewing the app's demonstrations and plain-language cues, as scored by an independent qualified trainer; a result below 85% falsifies the ability to deliver safety guidance at self-service scale.",
      "category": "feasibility",
      "quadrant": "q1"
    },
    {
      "id": "H1.4",
      "text": "At least 40% of users who complete a first workout will complete 8 or more workouts during the following 28 days when offered reminders, gradual progression, and low-pressure tracking; retention below 40% falsifies the assumption that the product can establish a repeatable beginner habit sufficient to support subscription retention.",
      "category": "desirability",
      "quadrant": "q1"
    },
    {
      "id": "H2.1",
      "text": "At least 70% of new users who report limited time, low energy, or a missed workout will choose and complete a 5–10 minute simplified routine rather than abandon the session when that option is presented; a rate below 70% falsifies the importance of adaptive short routines as a reliable recovery mechanism.",
      "category": "desirability",
      "quadrant": "q2"
    },
    {
      "id": "H2.2",
      "text": "For 90% or more of users who report knee, wrist, or back discomfort during onboarding, the workout-planning system will return a clinically approved substitute routine in under 2 seconds with no excluded movement included; performance below 90% falsifies the operational feasibility of personalized low-impact alternatives.",
      "category": "feasibility",
      "quadrant": "q2"
    },
    {
      "id": "H3.1",
      "text": "At least 10% of active monthly users will book and pay for one optional 15-minute coach form-review session within 60 days when sessions cost US$15–25; a booking rate below 10% falsifies the coach-session transaction fee as a meaningful secondary revenue stream.",
      "category": "viability",
      "quadrant": "q3"
    }
  ]
}
```
