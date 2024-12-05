import requests
import os
import json
import yaml
import re
from openai import OpenAI

class DartAgent():
    def __init__(self):
        self.api_key = os.getenv('DART_API_KEY')
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        if self.api_key is None or self.openai_api_key is None:
            raise Exception('DART_API_KEY or OPENAI_API_KEY not found in .env file or environment. Check if dotenv have been loaded.')
        self.client = OpenAI(api_key = self.openai_api_key)

    def extract_api_code(self, xml_response):
        """
        Extracts the API code from an XML formatted response using regex.

        Parameters:
        xml_response (str): The XML response string.

        Returns:
        str: The extracted API code, or an empty string if not found.
        """
        try:
            # Debugging: Print the XML response
            print("XML Response:", xml_response)

            # Use regex to find the api_code pattern
            match = re.search(r'<api_code>(.*?)</api_code>', xml_response)

            # If a match is found, return the matched group, else return an empty string
            return match.group(1) if match else ''
        except Exception as e:
            # Debugging: Print the error
            print("Error:", e)
            return 'Error extracting API code'

    def get_dart_code(self, query):
        two_shot_prompt = [
            {
                "role": "user",
                "content": "삼성전자에 대한 배당 상세 정보가 필요합니다. 현재와 이전 년도의 데이터를 포함해서요."
            },
            {
                "role": "assistant",
                "content": """<thought>
        The user is requesting detailed information about dividends for Samsung Electronics, including data from the current and previous years. This request aligns with API code B18, which provides information about dividends for different years, focusing on common stock cash dividends per share.
</thought>
<response>
<api_code>B18</api_code>
</response>"""
            },
            {
                "role": "user",
                "content": "현대자동차의 전체 회계 항목을 포함한 재무제표를 제공할 수 있나요?"
            },
            {
                "role": "assistant",
                "content": """<thought>
        The user is asking for a comprehensive financial statement of Hyundai Motor Company, including a detailed view of all account items. The appropriate API code for this request is C4, which offers access to the entire set of account items in the XBRL financial statements submitted by non-financial listed companies.
</thought>
<response>
<api_code>C4</api_code>
</response>"""
            }
        ]
        _prompt = [
            {
                "role":"system",
                "content": """Instruction: For given user query, return the corresponding DART API code.
---API codes and short description.
## Here is a set of code and short description about the API.

공시정보 목록:
- 코드: A2
API 내용: DART에 등록되어있는 기업의 개황정보를 제공합니다.

사업보고서 주요정보 목록:
- 코드: B1
API 내용: 조건부 자본증권 미상환 잔액을 남은 연 수로 나눠 제공합니다.
- 코드: B2
API 내용: 미등기임원 보수 통계를 제공합니다.
- 코드: B3
API 내용: 회사채 미상환 잔액을 남은 연 수로 나눠 제공합니다.
- 코드: B4
API 내용: 단기사채 미상환 잔액을 남은 일 수로 나눠 제공합니다.
- 코드: B5
API 내용: 기업어음증권 미상환 잔액을 남은 연 수로 나눠 제공합니다.
- 코드: B6
API 내용: 채무증권 발행회사, 증권종류, 발행 일자, 총액, 이자율 등의 채무증권 관련 정보를 제공합니다.
- 코드: B7
API 내용: 사모자금의 사용내역을 제공합니다.
- 코드: B8
API 내용: 공모자금의 사용내역 - 납입금액, 자금 사용내역, 계획 등을 제공합니다.
- 코드: B9
API 내용: 이사·감사 전체의 보수현황(주주총회 승인금액)을 제공합니다.
- 코드: B10
API 내용: 이사·감사 전체의 보수현황(보수지급금액 - 유형별)을 제공합니다.
- 코드: B11
API 내용: 주식의 총수 현황 - 발행할 주식 수, 발행한 주식 수, 감소한 주식 수 등을 제공합니다.
- 코드: B12
API 내용: 회계감사인의 명칭 및 감사의견을 제공합니다.
- 코드: B13
API 내용: 감사용역체결현황을 제공합니다.
- 코드: B14
API 내용: 회계감사인과의 비감사용역 계약체결 현황을 제공합니다.
- 코드: B15
API 내용: 사외이사 및 그 변동현황을 제공합니다.
- 코드: B16
API 내용: 신종자본증권 미상환 잔액을 남은 연 수로 나눠 제공합니다.
- 코드: B17
API 내용: 증자(감자) - 주식 발행 감소 - 현황을 제공합니다.
- 코드: B18
API 내용: 배당에 관한 사항 - 당기, 전기, 전전기로 나눠 - 제공합니다. 보통주의 주당 현금배당금이 중요합니다.
- 코드: B19
API 내용: 자기주식 취득 및 처분 관련 현황을 제공합니다.
- 코드: B20
API 내용: 최대주주 현황을 제공합니다.
- 코드: B21
API 내용: 최대주주 변동현황을 기초 지분, 기말 지분 등으로 나눠 제공합니다.
- 코드: B22
API 내용: 소액주주 관련 정보를 제공합니다.
- 코드: B23
API 내용: 임원 현황 - 출생년월(나이), 주요 경력, 임기 만료 등 정보를 제공합니다.
- 코드: B24
API 내용: 직원 현황을 - 전 직원 수, 정규직 수, 평균 급여액 등 정보를 제공합니다.
- 코드: B25
API 내용: 이사·감사의 개인별 보수 현황을 제공합니다.
- 코드: B26
API 내용: 이사·감사 전체의 보수현황을 제공합니다.
- 코드: B27
API 내용: 개인별 보수지급 금액(5억이상 상위5인)을 제공합니다.
- 코드: B28
API 내용: 타법인 출자현황을 제공합니다.

상장기업 재무정보 목록:
- 코드: C1
API명: 단일회사 주요계정
API 내용: 상장법인(금융업 제외)이 제출한 정기보고서 내에 XBRL재무제표의 주요계정과목(재무상태표, 손익계산서)을 제공합니다.
- 코드: C2
API명: 다중회사 주요계정
API 내용: 상장법인(금융업 제외)이 제출한 정기보고서 내에 XBRL재무제표의 주요계정과목(재무상태표, 손익계산서)을 제공합니다. (상장법인 복수조회 가능)
- 코드: C3
API명: 재무제표 원본파일(XBRL)
API 내용: 상장법인이 제출한 정기보고서 내에 XBRL재무제표의 원본파일(XBRL)을 제공합니다.
- 코드: C4
API명: 단일회사 전체 재무제표
API 내용: 상장법인(금융업 제외)이 제출한 정기보고서 내에 XBRL재무제표의 모든계정과목을 제공합니다.
- 코드: C5
API명: XBRL택사노미재무제표양식
API 내용: 금융감독원 회계포탈에서 제공하는 IFRS 기반 XBRL 재무제표 공시용 표준계정과목체계(계정과목) 을 제공합니다.

지분공시 종합정보 목록:
- 코드: D1
API명: 대량보유 상황보고
API 내용: 주식등의 대량보유상황보고서 내에 대량보유 상황보고 정보를 제공합니다.
- 코드: D2
API명: 임원ㆍ주요주주 소유보고
API 내용: 임원ㆍ주요주주특정증권등 소유상황보고서 내에 임원ㆍ주요주주 소유보고 정보를 제공합니다.
- 코드: E6
API명: 무상증자결정
API 내용: 무상증자 결정에 대한 정보를 제공합니다.

-- Specification
- When giving your result, always give your response in xml format with two node: <thought> and <response>, where
    - <thought> is your though or planning, reasoning for your response, must ALWAYS be in English.
    - <response> is the api code in xml format."""
            }
        ] + two_shot_prompt
        response = self.client.chat.completions.create(
            model= 'gpt-4-turbo-preview',
            messages= _prompt
        )
        return self.extract_api_code(response.choices[0].message.content).strip()

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    dart_agent = DartAgent()
    print(dart_agent.get_dart_code('삼성전자의 임원 중 가장 높은 연봉을 받는 사람은 누구인가?'))