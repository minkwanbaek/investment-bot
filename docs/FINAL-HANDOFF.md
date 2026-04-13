# Investment Bot Final Handoff

## 완료 범위
- BOT-001 ~ BOT-028 구현 및 테스트 완료
- 설정 외부화 1차/2차 완료
- 운영 서비스 재시작 및 핵심 API 반영 확인
- 대시보드 UI를 `/operator/live-dashboard` 응답 구조에 맞게 정리
- 실거래 체크리스트 API `/operator/deploy-checklist` 추가

## 핵심 실행 경로
- 서비스: `investment-bot.service`
- 실행 python: `.venv/bin/python`
- API 포트: `8899`
- 설정 파일: `config/app.yml`

## 주요 확인 엔드포인트
- `/health`
- `/config`
- `/operator/live-dashboard`
- `/operator/deploy-checklist`

## 테스트
```bash
cd /home/javajinx7/.openclaw/workspace/projects/investment-bot
PYTHONPATH=src ./.venv/bin/pytest tests/test_auto_trade_service.py -q
```

## 다음 운영 작업 후보
1. 실거래 체크리스트 저장/승인 로그 연결
2. 대시보드에 equity curve 시각화 추가
3. walkforward / paper compare 결과를 UI에 연결
4. 설정 구조 평면 필드 리팩터링
