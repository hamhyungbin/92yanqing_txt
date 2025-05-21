import requests
from bs4 import BeautifulSoup
import re # 정규 표현식 모듈
from urllib.parse import urljoin # 상대 URL을 절대 URL로 변환하기 위함
import time # 시간 지연을 위함

def sanitize_filename(filename):
    """
    문자열을 안전한 파일명으로 변환합니다.
    &nbsp; (U+00A0)를 포함한 공백을 처리하고, 유효하지 않은 문자들을 제거/대체합니다.
    """
    if not filename:
        return "untitled"
    # &nbsp; (non-breaking space, U+00A0)는 이미 처리되었거나 extract_title_for_filename에서 고려됨.
    # 여기서는 일반 공백 및 기타 문자 처리.
    filename = filename.strip() # 앞뒤 공백 먼저 제거
    filename = re.sub(r'\s+', '_', filename) # 여러 공백을 하나의 언더스코어로 대체
    filename = re.sub(r'[\\/*?:"<>|]', '', filename) # 파일명으로 사용할 수 없는 문자 제거
    filename = filename[:200] # 파일명 길이 제한 (예: 200자)
    if not filename or filename.strip('.') == "" or filename.lower() == "untitled": # 추가: 입력이 "untitled"여도 그대로 반환
        return "untitled"
    return filename

def extract_title_for_filename(soup):
    """
    BeautifulSoup 객체에서 <span class="title">을 찾아 파일명으로 사용할 문자열을 추출하고 정제합니다.
    &nbsp;&nbsp; (두 개의 연속된 공백) 뒤의 텍스트를 사용합니다.
    """
    output_filename_base = "untitled" # 기본 파일명
    title_span = soup.find('span', class_='title')
    
    if title_span:
        raw_title_text = title_span.get_text() # &nbsp;는 \xa0 문자로 변환됨
        
        # BeautifulSoup은 &nbsp;&nbsp;를 '\xa0\xa0' (두 개의 연속된 non-breaking space)로 변환합니다.
        separator = '\xa0\xa0' 

        if separator in raw_title_text:
            try:
                # 구분자(&nbsp;&nbsp;)를 기준으로 문자열을 나누고, 그 뒷부분을 가져옵니다.
                filename_candidate = raw_title_text.split(separator, 1)[1]
                cleaned_candidate = filename_candidate.strip() # 앞뒤 공백 제거
                
                if cleaned_candidate: # 실제 내용이 있다면 파일명으로 사용
                    output_filename_base = cleaned_candidate
                # cleaned_candidate가 비어있으면 output_filename_base는 "untitled"로 유지됩니다.
            except IndexError:
                # split 후 [1] 인덱스가 없는 경우 (예: 문자열이 구분자로 끝나는 경우)
                # 이 경우 구분자 뒤에 내용이 없는 것이므로 "untitled"로 유지됩니다.
                pass 
        # 구분자(&nbsp;&nbsp;)가 텍스트 내에 없으면 output_filename_base는 "untitled"로 유지됩니다.
            
    return sanitize_filename(output_filename_base) # 최종적으로 한번 더 sanitize

def extract_relevant_paragraphs(soup):
    """
    BeautifulSoup 객체에서 조건에 맞는 <p> 태그의 텍스트 리스트를 추출합니다.
    (class 속성 없고, header/footer/nav/aside 내부에 있지 않음)
    """
    paragraphs_text = []
    for p_tag in soup.find_all('p'):
        if p_tag.has_attr('class'):
            continue

        is_in_excluded_section = False
        for parent in p_tag.parents:
            if parent.name in ['header', 'footer', 'nav', 'aside']: # 제외할 부모 태그 목록
                is_in_excluded_section = True
                break
        if is_in_excluded_section:
            continue

        text = p_tag.get_text(strip=True)
        if text:
            paragraphs_text.append(text)
    return paragraphs_text

def crawl_and_save_all_pages(initial_url):
    """
    초기 URL부터 시작하여 페이지네이션을 따라가며 내용을 크롤링하고 하나의 파일에 저장합니다.
    """
    current_url = initial_url
    output_filename = None
    first_page_processed = False

    while current_url:
        print(f"페이지 처리 중: {current_url}")
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(current_url, headers=headers, timeout=15)
            response.raise_for_status()
            response.encoding = response.apparent_encoding
            soup = BeautifulSoup(response.text, 'html.parser')

        except requests.exceptions.Timeout:
            print(f"URL 요청 시간 초과: {current_url}. 중단합니다.")
            current_url = None 
            continue
        except requests.exceptions.RequestException as e:
            print(f"URL 요청 오류 ({current_url}): {e}. 중단합니다.")
            current_url = None 
            continue
        except Exception as e: 
            print(f"페이지 처리 중 오류 ({current_url}): {e}. 중단합니다.")
            current_url = None 
            continue

        if not first_page_processed:
            filename_base = extract_title_for_filename(soup) # 수정된 로직 호출
            output_filename = f"{filename_base}.txt"
            file_mode = 'w'
            first_page_processed = True
            print(f"결과 파일명: {output_filename}")
        else:
            file_mode = 'a' 

        paragraphs = extract_relevant_paragraphs(soup)

        if paragraphs or file_mode == 'w': 
            try:
                with open(output_filename, file_mode, encoding='utf-8') as f:
                    if file_mode == 'a' and paragraphs:
                        f.write("\n\n") 
                    
                    for i, text_content in enumerate(paragraphs):
                        f.write(text_content)
                        if i < len(paragraphs) - 1: 
                            f.write("\n\n")
                
                if paragraphs:
                    print(f"{len(paragraphs)}개의 단락을 '{output_filename}'에 추가했습니다.")
                elif file_mode == 'w':
                     print(f"'{output_filename}' 파일이 생성되었습니다 (첫 페이지 내용 없음 또는 내용 없음).")

            except IOError as e:
                print(f"파일 쓰기 오류 ({output_filename}): {e}. 중단합니다.")
                current_url = None 
                continue
        elif file_mode == 'a': 
            print(f"'{current_url}' 페이지에서 추가할 내용이 없습니다.")

        next_page_link_tag = soup.find('a', id='pt_next', class_='Readpage_up')

        if not next_page_link_tag:
            print("다음 페이지 링크 요소를 찾을 수 없습니다. 크롤링을 종료합니다.")
            current_url = None 
            continue

        next_href = next_page_link_tag.get('href')
        
        if not next_href or not next_href.strip():
            print("다음 페이지 링크에 href 속성이 없거나 비어있습니다. 크롤링을 종료합니다.")
            current_url = None 
            continue
            
        next_href = next_href.strip() 
        print(f"찾은 다음 페이지 href: '{next_href}'")

        if next_href.lower() == 'javascript:void(0);':
            print("마지막 페이지에 도달했습니다 (href가 'javascript:void(0);'). 크롤링을 종료합니다.")
            current_url = None 
            continue
        
        new_url = urljoin(current_url, next_href)

        if new_url == current_url:
            print(f"경고: 다음 URL ('{new_url}')이 현재 URL과 동일합니다. href: '{next_href}'. 무한 루프 방지를 위해 중단합니다.")
            current_url = None 
        else:
            current_url = new_url
        
        if current_url: 
            print("다음 페이지로 이동 전 1초 대기...")
            time.sleep(1) 

    if output_filename:
        print(f"\n모든 크롤링 작업 완료. 전체 내용이 '{output_filename}'에 저장되었습니다.")
    elif initial_url : 
        print("\n크롤링 작업 완료. 파일이 생성되지 않았습니다 (예: 초기 URL 접근 실패).")
    else:
        print("\n크롤링 작업이 시작되지 않았습니다.")


if __name__ == "__main__":
    initial_target_url = input("텍스트를 추출할 시작 웹 페이지 URL을 입력하세요: ")
    if initial_target_url and initial_target_url.strip():
        crawl_and_save_all_pages(initial_target_url.strip())
    else:
        print("유효한 URL이 입력되지 않았습니다.")