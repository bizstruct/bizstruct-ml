"""The judge must not grade the generator's own family."""


class FamilyGuardError(RuntimeError):
    """Generator and judge are from the same model family."""


def assert_different_family(generator_family: str, judge_family: str) -> None:
    """Raise `FamilyGuardError` if both families are equal (case-insensitive).

    Called at worker startup: a judge from the generator's family shares its
    blind spots, so the worker refuses to start rather than run that way.
    """
    if generator_family.strip().lower() == judge_family.strip().lower():
        raise FamilyGuardError(
            f"judge family '{judge_family}' equals generator family '{generator_family}'; "
            "the judge must be a different model family"
        )
