import dataclasses
import itertools

import pytest
from solution import Version, bump, compare, parse, satisfies, sort_versions

# The ordering example from the SemVer 2.0.0 specification, in ascending precedence.
SPEC_ORDER = [
    "1.0.0-alpha",
    "1.0.0-alpha.1",
    "1.0.0-alpha.beta",
    "1.0.0-beta",
    "1.0.0-beta.2",
    "1.0.0-beta.11",
    "1.0.0-rc.1",
    "1.0.0",
]


def test_version_is_a_frozen_dataclass():
    names = [f.name for f in dataclasses.fields(Version)]
    assert names == ["major", "minor", "patch", "prerelease", "build"]
    with pytest.raises(dataclasses.FrozenInstanceError):
        parse("1.2.3").major = 9


def test_parse_plain_version():
    assert parse("1.2.3") == Version(1, 2, 3, (), ())
    assert parse("0.0.0") == Version(0, 0, 0, (), ())
    assert parse("10.20.30") == Version(10, 20, 30, (), ())


def test_parse_prerelease_and_build():
    assert parse("1.2.3-alpha.1") == Version(1, 2, 3, ("alpha", "1"), ())
    assert parse("1.2.3+build.5") == Version(1, 2, 3, (), ("build", "5"))
    assert parse("1.2.3-rc.1+exp.sha.5114f85") == Version(
        1, 2, 3, ("rc", "1"), ("exp", "sha", "5114f85")
    )
    assert parse("1.0.0-x-y-z.--") == Version(1, 0, 0, ("x-y-z", "--"), ())
    assert parse("1.0.0-0") == Version(1, 0, 0, ("0",), ())
    assert parse("1.0.0+001") == Version(1, 0, 0, (), ("001",))
    assert parse("1.0.0-0a") == Version(1, 0, 0, ("0a",), ())


@pytest.mark.parametrize(
    "text",
    [
        "",
        "1",
        "1.2",
        "1.2.3.4",
        "v1.2.3",
        " 1.2.3",
        "1.2.3 ",
        "01.2.3",
        "1.02.3",
        "1.2.03",
        "1.2.x",
        "-1.2.3",
        "1.2.3-",
        "1.2.3+",
        "1.2.3-alpha..1",
        "1.2.3-.alpha",
        "1.2.3-alpha.",
        "1.2.3-01",
        "1.2.3-alpha.01",
        "1.2.3-al_pha",
        "1.2.3+build..1",
        "1.2.3+bu!ld",
        "1.2.3-alpha+",
        "1.2.3+a+b",
    ],
)
def test_parse_rejects_invalid_versions(text):
    with pytest.raises(ValueError):
        parse(text)


def test_compare_core_numbers_numerically():
    assert compare("1.2.3", "1.2.3") == 0
    assert compare("1.2.3", "1.2.4") == -1
    assert compare("1.10.0", "1.9.0") == 1
    assert compare("2.0.0", "10.0.0") == -1
    assert compare("1.0.9", "1.1.0") == -1


def test_spec_ordering_holds_for_every_pair():
    for (i, low), (j, high) in itertools.combinations(enumerate(SPEC_ORDER), 2):
        assert i < j
        assert compare(low, high) == -1, (low, high)
        assert compare(high, low) == 1, (high, low)


def test_prerelease_identifier_rules():
    assert compare("1.0.0-2", "1.0.0-11") == -1  # numeric, not string, comparison
    assert compare("1.0.0-11", "1.0.0-a") == -1  # numeric is lower than non-numeric
    assert compare("1.0.0-a", "1.0.0-B") == 1  # ASCII order: "B" < "a"
    assert compare("1.0.0-a.b", "1.0.0-a.b.0") == -1  # fewer identifiers is lower
    assert compare("1.0.0-1a", "1.0.0-2") == 1  # "1a" is non-numeric
    assert compare("1.0.0-alpha", "1.0.0-alpha") == 0


def test_build_metadata_is_ignored():
    assert compare("1.0.0+a", "1.0.0+b") == 0
    assert compare("1.0.0-rc.1+x", "1.0.0-rc.1") == 0
    assert compare("1.0.0+zzz", "1.0.1") == -1


def test_compare_rejects_invalid_versions():
    with pytest.raises(ValueError):
        compare("1.0", "1.0.0")
    with pytest.raises(ValueError):
        compare("1.0.0", "nope")


def test_sort_versions():
    shuffled = [SPEC_ORDER[i] for i in (5, 2, 7, 0, 4, 1, 6, 3)]
    assert sort_versions(shuffled) == SPEC_ORDER
    assert sort_versions(["2.0.0", "1.0.0", "1.10.0", "1.9.0"]) == [
        "1.0.0",
        "1.9.0",
        "1.10.0",
        "2.0.0",
    ]
    assert sort_versions([]) == []


def test_sort_is_stable_and_does_not_modify_the_input():
    versions = ["1.0.0+b", "0.9.0", "1.0.0+a", "1.0.0"]
    assert sort_versions(versions) == ["0.9.0", "1.0.0+b", "1.0.0+a", "1.0.0"]
    assert versions == ["1.0.0+b", "0.9.0", "1.0.0+a", "1.0.0"]


def test_bump():
    assert bump("1.2.3", "patch") == "1.2.4"
    assert bump("1.2.3", "minor") == "1.3.0"
    assert bump("1.2.3", "major") == "2.0.0"
    assert bump("1.2.3-alpha+7", "patch") == "1.2.4"
    assert bump("0.9.9-rc.1", "minor") == "0.10.0"
    assert bump("9.9.9+meta", "major") == "10.0.0"


def test_bump_rejects_bad_input():
    with pytest.raises(ValueError):
        bump("1.2.3", "prerelease")
    with pytest.raises(ValueError):
        bump("1.2", "patch")


def test_exact_and_comparison_ranges():
    assert satisfies("1.2.3", "1.2.3")
    assert satisfies("1.2.3+build", "=1.2.3")
    assert not satisfies("1.2.4", "1.2.3")
    assert satisfies("1.2.4", ">1.2.3")
    assert not satisfies("1.2.3", ">1.2.3")
    assert satisfies("1.2.3", ">=1.2.3")
    assert satisfies("1.2.2", "<1.2.3")
    assert satisfies("1.2.3", "<=1.2.3")
    assert not satisfies("1.2.4", "<=1.2.3")


def test_tilde_range():
    assert satisfies("1.2.3", "~1.2.3")
    assert satisfies("1.2.99", "~1.2.3")
    assert not satisfies("1.2.2", "~1.2.3")
    assert not satisfies("1.3.0", "~1.2.3")


def test_caret_range():
    assert satisfies("1.2.3", "^1.2.3")
    assert satisfies("1.99.0", "^1.2.3")
    assert not satisfies("2.0.0", "^1.2.3")
    assert not satisfies("1.2.2", "^1.2.3")


def test_caret_range_below_one():
    assert satisfies("0.2.9", "^0.2.3")
    assert not satisfies("0.3.0", "^0.2.3")
    assert satisfies("0.0.3", "^0.0.3")
    assert not satisfies("0.0.4", "^0.0.3")
    assert satisfies("0.0.0", "^0.0.0")
    assert not satisfies("0.0.1", "^0.0.0")


def test_ranges_use_precedence_only_for_prereleases():
    assert satisfies("2.0.0-alpha", "^1.2.3")
    assert satisfies("1.3.0-rc.1", "~1.2.3")
    assert not satisfies("1.2.3-beta", "^1.2.3")
    assert satisfies("1.0.0-rc.2", ">=1.0.0-rc.1")
    assert not satisfies("1.0.0-beta", ">=1.0.0-rc.1")
    assert satisfies("1.0.0-rc.1", "<1.0.0")


def test_comparators_are_combined_with_and():
    assert satisfies("1.5.0", ">=1.2.0 <2.0.0")
    assert not satisfies("2.0.0", ">=1.2.0 <2.0.0")
    assert not satisfies("1.1.9", ">=1.2.0 <2.0.0")
    assert satisfies("1.4.2", "^1.2.0 <1.5.0 >1.4.1")
    assert satisfies("1.5.0", ">=1.2.0   <2.0.0")


@pytest.mark.parametrize(
    "range_spec",
    ["", "   ", "^1.2", ">=", "~>1.2.3", "1.2.3 ||", "^^1.2.3", "=>1.2.3", "*", "<1.2.x"],
)
def test_invalid_ranges_are_rejected(range_spec):
    with pytest.raises(ValueError):
        satisfies("1.2.3", range_spec)


def test_satisfies_rejects_an_invalid_version():
    with pytest.raises(ValueError):
        satisfies("1.2", "^1.2.3")
