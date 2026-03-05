import time

print("===베스천 지휘 통제소 가동===")
time.sleep(1)

while True:
    print("-" * 30)
    target = input("공격할 타겟을 입력하세요 (시스템 종료는 '종료' 입력): ")
    time.sleep(1)

    if target == '종료':
        print(f"삐빅... 시스템을 종료합니다 수고하셨습니다")
        break
    elif target == "겐지":
        print(f"겐지 발견! 튕겨내기 지속시간이 끝날 때까지 대기합니다...")
        time.sleep(2)
        print("두두두두! 겐지 제압 완료")
    elif target == "디바":
        print("디바의 방어 매트릭스 전개! 레이저 무기로 공격합니다 지이잉")
    else:
        print(f" {target}확인. 기관총 발사! 두두두두두두!")