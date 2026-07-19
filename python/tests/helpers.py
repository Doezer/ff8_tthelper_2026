"""Test-construction helpers. Ported from TestHelpers.fs."""

from ff8_tthelper_py.domain_types import Card, Element, PlayGridSlot


def card(powers, owner, power_modifier, element):
    return Card(tuple(powers), power_modifier, owner, element)


def hc(powers, owner, element):
    return card(powers, owner, 0, element)


def pce(powers, owner, power_modifier, elem):
    return PlayGridSlot.full(card(powers, owner, power_modifier, elem))


def pc(powers, owner, power_modifier):
    return pce(powers, owner, power_modifier, Element.UNKNOWN)


empty_slot = PlayGridSlot.empty()


def empty_slot_elem(elem):
    return PlayGridSlot.empty(elem)


n = None
e = Element.EARTH
f = Element.FIRE
h = Element.HOLY
i = Element.ICE
p = Element.POISON
t = Element.THUNDER
w = Element.WIND
a = Element.WATER
u = Element.UNKNOWN
