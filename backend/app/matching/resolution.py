import re
from dataclasses import dataclass

@dataclass(frozen=True)
class ResolutionCompatibility:
    compatible:bool; confidence:float; warnings:list[str]; differences:list[str]

CONFLICTS=[("regulation",("overtime","penalties","advance")),("90 minutes",("overtime","penalties","advance")),("常规时间",("加时","点球","晋级")),("closing price",("intraday","high price"))]

def resolution_compatibility(left:str,right:str)->ResolutionCompatibility:
    a,b=left.lower(),right.lower(); differences=[]
    for anchor,others in CONFLICTS:
        if (anchor in a and any(x in b for x in others)) or (anchor in b and any(x in a for x in others)):differences.append(f"规则范围冲突: {anchor}")
    nums_a=re.findall(r"(?:over|above|below|under|超过|高于|低于)\s*\$?([0-9,.]+)",a); nums_b=re.findall(r"(?:over|above|below|under|超过|高于|低于)\s*\$?([0-9,.]+)",b)
    if nums_a and nums_b and nums_a[0].replace(",","")!=nums_b[0].replace(",",""):differences.append(f"阈值不一致: {nums_a[0]} vs {nums_b[0]}")
    dates_a=set(re.findall(r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2}",a)); dates_b=set(re.findall(r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2}",b))
    if dates_a and dates_b and dates_a!=dates_b:differences.append("规则日期截止不一致")
    enough=min(len(a),len(b))>=40
    confidence=.9 if enough and not differences else .55 if not differences else .1
    return ResolutionCompatibility(not differences and enough,confidence,["⚠ "+x for x in differences],differences)

def resolution_warnings(left:str,right:str)->list[str]:return resolution_compatibility(left,right).warnings
