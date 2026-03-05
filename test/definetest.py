import time

#1. 스킬(함수) 가르치기 (정의하기)
def shoot_target(target_name):
    print(f"\n---삐빅.[{target_name}] 스캔중---")

    time.sleep(1.5)

    if target_name == "겐지":
        print("경고: 겐지의 튕겨내기가 예상됩니다! 사격을 취소합니다")
    elif target_name == "디바":
        print("방어 매트릭스 주의: 레이저 무기로 교체하여 공격합니다")
    else:
        print(f"두두두두두{target_name}을 공격합니다")

print("전투 준비 완료 3초 뒤 감시 모드를 시작합니다")
time.sleep(3)


enemy_list = ["트레이서", "겐지", "윈스턴", "디바"]
for target in enemy_list:
    shoot_target(target)
    time.sleep(1)


enemy_info = {
    "트레이서" : 150,
    "겐지" : 250,
    "윈스턴" : 500,
    "디바" : 350,
    "라인하르트" : 1000
}

print(f"---적군 HP 스캔 시작 ---")
for name,hp in enemy_info.items():
    print(f"스캔대상 : {name} / 예상 체력 : {hp}")
    time.sleep(1)

    if hp >= 500:
        print("---> 체력이 높은 탱커입니다! 집중 공격이 필요합니다")
    else:
        print("---> 체력이 낮습니다. 가볍게 제압 가능합니다.\n")
print("--- 스캔 완료 ---")

