"""
CO2 sensor fault model for the greenhouse simulation.

The student kit ships this module encoded. The GHU-2 commissioning report
describes the faults it produces.
"""

import base64
import zlib

_SOURCE = (
    "c-oa$TTk3L6n@XI@bZ+<Fq#YOu0}gm(Q4=-u@q6-hegN=6KC*}*dxaSWh?%BPn?VG*kMziGCAiv*"
    "Uz6rCU}9;L?)X&DN9l!TI{%x`c)8IU4J?|zgT}pEA%};@OQ9%*v}4@%`f#P6NLOn@KciS2^I<460"
    "l!#Mq=%g3Ytm06Z{_Uh`^;JJ8+s#rjAd#7m1{t)sb)sZs837KCOJwY+64>4h%p|a=hCWHS7pHPvR"
    "=ei3{LaRuYMGT2NU*teRiruG#sBX2V5O9zO9`*Kd42nUbT$sNR3W^E&wPqJA3P`>bkxHmdXEX}1b"
    "!{WS<a{`F;s&#u?&f7bZx>BW~dzCOMDxCR=8i(l(<j;mUN;QaFZ=KS=+cD}m$8(dY?AP7EmgbD@O"
    "iPc$>mm~_*8+4ZJbNN|93(G(i&`h`**%D<rPo()8MuZE>hAhc9kHuKl67l<g$)+~z-I$<m75zMh!"
    "A@gr!3(J^K8)IdRZ~-PvXS%&s=enthe@i5nRdcbENKB8X@Y`NHEgGA*st~&+Lck!VB*^RR$il7MZ"
    "+PFhJRLNHBnNMAx56zlt7RW7L(DOV3rglHfhnFq}bTKb#P*Ic*viK5Huxav{cDyhRleFafv8Ht->"
    "w4V<Hk-67;ni-&zPR!t7wr9vOdT=+94clvRXnLxDD!L4Ogi2ayT{9ZJf!CG?ikjSSl~x2F4D?VE9"
    "d9?46L)XJ)&y4ojHlA;VFT^+OmzHRkw8g17d+`R0Z2I}G)6ci7kbj@bnw_v%0;#En?Du~<*W}Mfs"
    "0~xzndH2-!Y);o|V12jKJ3l1(HVB!y5aZmhy1sl0Za}pr7!aR`JD9eoKFksIJF7iQRmOm44!Bhw2"
    "kl%8zSONcjX}G)m4Z1?=Za}?QFF-QfD4K1O@!*S$4IbkjI_Qqlvl=yrHa7H8_|%`GHWon=pV{4=g"
    "%>EpxXy9Ss;T42+rZa#pfpL<P`!!>61O9aE^<xOJw(|=3=$F*$Y9KY>JFgx9W0LeTZn)(gs9J^^u"
    "}ayJ2hlve;<UZR)!_!oIwNhg~3gXC!lgTJ?M5aGap1*o6ZBA}6T6D2zL#ks+g&ddx}sl&}qXd&Cl"
    "#WW!l%+zB3nSz_Cp!u!<_=WGe~^HyJ{B=6_0<ORL2`n2*_!vuDwya*%ohYPXOwqx;b!4}^bxo_Jo"
    "7+v_!=^!_vz#gpiRWW9+&Uc1qtUW60sruY3YPKx$IeO_<@2VurF|c>5q0EN{_pC@tB70|7y|cVvU"
    "bQ0#Ky~xmBJjV>z+S^66(B~i`LKEP`$tiqp!)i&`H6szeqI`1)WIl9T4EKu3T6`WXN9yCU_p`;KQ"
    "5*%NP_a=4WC!d#xPD=zEnTolmylC;JxA9N+VSMOJkJ!G!eQA!+{Iv$Z9DHyx97`H9e4WlOE67k@S"
    "Z!klCS1@B_D|Lah"
)

exec(compile(zlib.decompress(base64.b85decode(_SOURCE)), "<encoded>", "exec"))
