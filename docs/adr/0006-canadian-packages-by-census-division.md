# Canadian packages are cut by census division and use NENA fields with CLDXF-CA values

Canada has no county layer everywhere, so a Canadian **Package** covers one Statistics Canada census
division (a county, regional municipality or district), with each census subdivision (municipality) as a
**Source agency** inside it; the province is the build job, as a state is in the US. Census division
boundaries cover the whole country and are open under the Open Government Licence – Canada. Packages keep
the NENA-STA-006.3 fields, which CRTC 2025-64 adopted as Canada's baseline, and fill them with CLDXF-CA
values (province codes in a1, for example), with Canada's domains beside the US ones in each package's
domains file. The trade-off: a census division is a statistical unit, not always the body that addresses
or answers 911 calls, so the **911 authority** for a Canadian package has to be named per province in the
jurisdiction registry rather than assumed from the unit.
