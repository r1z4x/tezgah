# The Turkish-I problem and its real failure: culture-independent strings are not prose

**What it is and claims.** The engineering rule is that culturally independent data - XML and HTML tags, user names, file paths, system object names - must be compared ordinally, because treating them as culture-sensitive produces subtle bugs and security issues; the canonical example is the Turkish dotless i. The documented failure: a build tool run under the Turkish locale (tr_TR) fails with No enum constant for FAILED, because uppercase i becomes dotted in Turkish and the identifier no longer matches, and the fix was never general.

**How it changes the skill.** A measured case where treating an identifier as language - case-folding it by locale - breaks a program. It is the strongest argument that the dev register's keep list is not pedantry, and that locale-sensitive handling of an identifier is a defect with a name.

**Quality.** Formal: a standard, a peer-reviewed paper or an institutional framework.
