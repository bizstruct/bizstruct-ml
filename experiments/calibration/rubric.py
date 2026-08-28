"""The five-criterion evaluation rubric (calibration brief). Text is
Ukrainian by design — this is what a Ukrainian-speaking human judge reads,
not code-facing content. Kept as plain data (no i18n machinery) so the
exact wording used for calibration is visible in one place and diffable.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Criterion:
    id: str  # "K1".."K5"
    title: str
    description: str
    levels: dict[int, str]  # 1, 3, 5 — the brief only defines these three


CRITERIA: list[Criterion] = [
    Criterion(
        id="K1",
        title="Узгодженість між артефактами",
        description=(
            "Чи описують усі артефакти одну й ту саму бізнес-модель. Дивитись: сегмент у карті "
            "емпатії ↔ персона в сценарії ↔ customer_segments у канвасі; обрана монетизація ↔ "
            "revenue_streams; болі клієнта ↔ ціннісні пропозиції; ключові ресурси ↔ структура "
            "витрат; гіпотези ↔ припущення канвасу."
        ),
        levels={
            1: "артефакти описують фактично різні бізнеси",
            3: "загальна лінія витримана, є одна-дві помітні розбіжності в деталях",
            5: "наскрізна узгодженість, кожен артефакт виводиться з попередніх",
        },
    ),
    Criterion(
        id="K2",
        title="Специфічність",
        description=(
            "Чи прив'язаний зміст до цієї конкретної ідеї. Робочий тест: підставити іншу ідею з "
            "тієї ж галузі — якщо текст лишається доречним, специфічність низька."
        ),
        levels={
            1: "переважно шаблонні формулювання, ідею можна замінити без шкоди",
            3: "частина змісту прив'язана до ідеї, частина — загальні місця",
            5: "конкретика в усіх артефактах: названі ролі, процеси, обмеження галузі",
        },
    ),
    Criterion(
        id="K3",
        title="Змістовна повнота",
        description=(
            "Чи розкрито кожен артефакт по суті. Оцінюється не наявність полів (її гарантує "
            "схема), а чи несе кожен пункт інформацію."
        ),
        levels={
            1: "формальне заповнення, пункти-заглушки, дублювання змісту між блоками",
            3: "основні блоки розкрито, окремі поверхові або повторюють сусідні",
            5: "кожен артефакт несе власний зміст, жоден не є переказом іншого",
        },
    ),
    Criterion(
        id="K4",
        title="Економічна правдоподібність",
        description=(
            "Чи тримається бізнес-логіка. Дивитись: чи є хтось, хто платить; чи співвідносяться "
            "витрати й надходження; чи відповідає канал збуту сегменту; чи не суперечить обраний "
            "патерн решті моделі."
        ),
        levels={
            1: "модель не працює економічно",
            3: "життєздатна, але є непроговорене сумнівне припущення",
            5: "економіка узгоджена, ризиковані припущення винесені в гіпотези",
        },
    ),
    Criterion(
        id="K5",
        title="Придатність гіпотез до перевірки",
        description="",
        levels={
            1: "гіпотези без критерію перевірки («клієнтам потрібен наш продукт»)",
            3: "конкретні, але спосіб перевірки неочевидний або результат неоднозначний",
            5: (
                "кожна гіпотеза містить перевірюване твердження, зрозумілий експеримент, "
                "покрито всі три категорії ризику"
            ),
        },
    ),
]

CRITERION_IDS: list[str] = [c.id for c in CRITERIA]

WHAT_DOES_NOT_AFFECT_SCORE: list[str] = [
    "обсяг тексту (довший артефакт не є кращим)",
    "впевненість тону",
    "форматування, структурованість",
    "граматика й стилістика",
    "кількість пунктів у блоці (п'ять поверхових гірші за три змістовні)",
]


def render_rubric_md(criteria_order: list[str]) -> str:
    """Renders the full rubric text in the given criterion order (see
    calibration/export.py — order is randomized per exported file)."""
    by_id = {c.id: c for c in CRITERIA}
    lines = ["## Рубрика оцінювання", "", "Шкала 1–5 по кожному критерію. Оцінюється **проєкт цілком**, не окремий блок.", ""]
    for cid in criteria_order:
        c = by_id[cid]
        lines.append(f"### {c.id}. {c.title}")
        lines.append("")
        if c.description:
            lines.append(c.description)
            lines.append("")
        lines.append(f"- **1** — {c.levels[1]}")
        lines.append(f"- **3** — {c.levels[3]}")
        lines.append(f"- **5** — {c.levels[5]}")
        lines.append("")

    lines.append("### Що НЕ впливає на оцінку")
    lines.append("")
    for item in WHAT_DOES_NOT_AFFECT_SCORE:
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


RESPONSE_FORMAT_MD = """## Формат відповіді

По кожному з п'яти критеріїв, у порядку, наведеному вище:

1. **Обґрунтування** (2–3 речення) — чому саме такий бал. Це йде ПЕРЕД балом: спершу поясни, потім став оцінку, а не навпаки.
2. **Бал** — ціле число від 1 до 5.
3. **Цитата** — коротка цитата з матеріалу нижче, що підтверджує бал.

Сумарний бал не виводити — жодного середнього чи підсумкового числа по всіх п'яти критеріях.
"""
