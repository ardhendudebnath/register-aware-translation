"""
East Asian: Japanese.

Three levels on the sentence-final politeness spine. Real keigo needs
morphological analysis rather than string swaps, which the blueprint
lists as a known gap (3.4).
"""

from __future__ import annotations

from typing import Tuple

from .model import LanguageTable, Rule


# --------------------------------------------------------------------------
# East Asian
# --------------------------------------------------------------------------

# --------------------------------------------------------------------------
# Japanese verb paradigms.
#
# Japanese is the one language here where register does not attach to a second
# person at all. です and ます mark the speaker's stance toward the *listener*,
# so "今日はいい天気です" is polite while being about the weather. Everything
# else in this project keys off a pronoun; Japanese keys off the sentence
# ending, and the table is a list of those endings.
#
# Each entry is (plain, ます, 敬語). The third column is honorific or humble
# vocabulary rather than an inflection — 見る becomes 拝見する, not 見られる —
# which is why real keigo needs morphological analysis and this table only
# claims the sentence-final spine.
# --------------------------------------------------------------------------

_JA_PARADIGMS: Tuple[Tuple[str, str, str, str], ...] = (
    # gloss,     plain,        masu,            keigo
    ("suru", "する", "します", "いたします"),
    ("suru.past", "した", "しました", "いたしました"),
    ("suru.neg", "しない", "しません", "いたしません"),
    ("iku", "行く", "行きます", "まいります"),
    ("iku.past", "行った", "行きました", "まいりました"),
    ("kuru", "来る", "来ます", "まいります"),
    ("kuru.past", "来た", "来ました", "まいりました"),
    ("miru", "見る", "見ます", "拝見します"),
    ("miru.past", "見た", "見ました", "拝見しました"),
    ("taberu", "食べる", "食べます", "いただきます"),
    ("nomu", "飲む", "飲みます", "いただきます"),
    ("iu", "言う", "言います", "申します"),
    ("iru", "いる", "います", "おります"),
    ("aru", "ある", "あります", "ございます"),
    ("nai", "ない", "ありません", "ございません"),
    ("morau", "もらう", "もらいます", "いただきます"),
    ("shiru", "知ってる", "知っています", "存じております"),
    ("kau", "買う", "買います", "お求めになります"),
    ("matsu", "待つ", "待ちます", "お待ちします"),
    ("hanasu", "話す", "話します", "お話しします"),
    ("kiku", "聞く", "聞きます", "伺います"),
    ("yomu", "読む", "読みます", "拝読します"),
    ("kaku", "書く", "書きます", "お書きします"),
    ("wakaru", "分かる", "分かります", "承知しております"),
    ("dekiru", "できる", "できます", "いたしかねます"),
    ("omou", "思う", "思います", "存じます"),
    ("au", "会う", "会います", "お目にかかります"),
    ("kaeru", "帰る", "帰ります", "失礼します"),
    ("tsukau", "使う", "使います", "使わせていただきます"),
    ("motsu", "持つ", "持ちます", "お持ちします"),
    ("suwaru", "座る", "座ります", "お掛けになります"),
    ("yasumu", "休む", "休みます", "お休みになります"),
    ("oshieru", "教える", "教えます", "お教えします"),
    ("mirareru", "見せる", "見せます", "お見せします"),
    ("ageru", "あげる", "あげます", "差し上げます"),
)

#: The bare copula only counts at the end of a clause.
#:
#: Japanese has no word boundaries, so matching is substring-based, and だ
#: occurs inside perfectly ordinary words — ください is く-だ-さい. Without this
#: the honorific "恐れ入りますが、少々お待ちください" detected as Casual with
#: full confidence, on the strength of the だ buried in ください.
_JA_CLAUSE_FINAL = r"(?:[。．.!?！？、，]|$|ね|よ|な|ぞ|わ)"


# --------------------------------------------------------------------------
# Japanese humble verbs collapse distinctions the plain forms keep, so one
# keigo form serves two verbs and the downgrade has to guess. いただきます is
# humble for 食べる and 飲む both; まいります for 行く and 来る.
#
# The object settles the first: 食べる takes food and 飲む takes drink, and the
# noun is right there in front of the verb. A destination settles the second.
# Without them the first-declared verb simply won, so "お茶をいただきます" came
# down to "お茶を食べる" — drinking tea rendered as eating it.
#
# The guards go on the *keigo* form alone. Put on the rule they would also
# bind 行く, and "明日行く。" would need a destination to be recognised at all.
# --------------------------------------------------------------------------

_JA_DRINK = r"(?:お茶|茶|水|お水|コーヒー|紅茶|ビール|お酒|酒|ジュース|ミルク|牛乳|スープ)を"
_JA_DESTINATION = r"(?:へ|に)"

#: verb -> (keigo form, pattern that must precede it, pattern that must not)
_JA_KEIGO_GUARDS = {
    "nomu": (_JA_DRINK, ""),
    "taberu": ("", _JA_DRINK),
    "iku": (_JA_DESTINATION, ""),
    "kuru": ("", _JA_DESTINATION),
    "nomu.past": (_JA_DRINK, ""),
    "taberu.past": ("", _JA_DRINK),
    "iku.past": (_JA_DESTINATION, ""),
    "kuru.past": ("", _JA_DESTINATION),
}


def _ja_verb_rules() -> Tuple[Rule, ...]:
    out = []
    for name, plain, masu, keigo in _JA_PARADIGMS:
        if len({plain, masu, keigo}) <= 1:
            continue
        require, forbid = _JA_KEIGO_GUARDS.get(name, ("", ""))
        guards = ((keigo, forbid, "", require, "", ""),) if (require or forbid) else ()
        out.append(
            Rule(f"v.{name}", (plain, plain, masu, keigo), name, form_guards=guards)
        )
    return tuple(out)


JAPANESE = LanguageTable(
    code="ja",
    name="Japanese",
    canon=(1, 1, 2, 3),
    boundary="none",
    please=("", "", "", ""),
    # Matching is longest-first, so the multi-character spines beat the bare
    # copula nested inside them without needing declaration order to say so.
    rules=_ja_verb_rules() + (
        Rule("polite.arigatou", ("ありがと", "ありがとう", "ありがとうございます", "誠にありがとうございます"), "thanks"),
        Rule("polite.gomen", ("ごめん", "ごめんね", "すみません", "申し訳ございません"), "sorry"),
        Rule("polite.onegai", ("頼む", "お願い", "お願いします", "お願いいたします"), "please"),
        # 恐れ入りますが used to fill both honorific slots, so it split its vote
        # and a request opening with it read as Polite. 恐縮ですが is the
        # ordinary polite hedge and 恐れ入りますが the deferential one.
        Rule("polite.osoreirimasu", ("悪いけど", "すみませんが", "恐縮ですが",
                                     "恐れ入りますが"), "excuse me, but"),
        # The request ladder. お待ちください is the polite request form and had
        # no rule at all, so "少々お待ちください。" read as nothing.
        Rule("polite.kudasai", ("待って", "待ってください", "お待ちください",
                                "お待ちくださいませ"), "please wait"),
        # The copula drops entirely before the question particle: plain
        # "これはいくらか。" against polite "これはいくらですか。". Rewriting です to
        # だ blindly produced "だか", which is not Japanese. Longer than cop.da,
        # so it wins the match; the bare か is clause-final only, or it would
        # fire inside から and every disjunction.
        Rule("cop.desu.ka", ("か", "か", "ですか", "でございますか"), "is …?",
             form_guards=(("か", "", "", "", _JA_CLAUSE_FINAL),)),
        # だ only counts clause-finally — see _JA_CLAUSE_FINAL. です needs no
        # such guard: it does not occur inside other words.
        Rule("cop.da", ("だ", "だ", "です", "でございます"), "is",
             form_guards=(("だ", "", "", "", _JA_CLAUSE_FINAL),)),
        Rule("greet.hello", ("やあ", "こんにちは", "こんにちは", "お世話になっております"), "hello"),
    ),
)

