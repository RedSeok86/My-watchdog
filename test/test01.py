# 1. 변수 설정
battery = 3  # 배터리가 3칸 남음
status = "경계중"

print(f"시스템 가동: {status}")

# 2. 반복문 (배터리가 있는 동안 계속 감시)
while battery > 0:
    print(f"--- 현재 배터리: {battery}% ---")
    print("주변을 스캔합니다... 띠리릭...")

    # 3. 상황 발생 (가정)
    target = "적군"  # 만약 스캔된 대상이 적군이라면?

    # 4. 조건문 (판단)
    if target == "적군":
        print("삐빅! 적 발견! 제압 사격 개시!")
    else:
        print("아군입니다. 통과시키십시오.")

    battery = battery - 1  # 스캔 1회당 배터리 1 소모
    print("")  # 빈 줄 띄우기

print("시스템 종료: 충전이 필요합니다.")