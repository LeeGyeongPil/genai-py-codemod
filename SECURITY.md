# 보안 정책 / Security policy

보안 취약점을 발견하셨다면 **공개 이슈 대신** 이 레포의 **Security → Report a vulnerability**(비공개 취약점 신고)로 알려 주세요. 확인 후 답변드리고, 고친 버전을 릴리스하면서 함께 안내합니다.

If you find a security issue, please **do not open a public issue**. Use **Security → Report a vulnerability** in this repository to report it privately. We will reply after checking and announce the fix with a release.

이 도구는 네트워크 서버를 띄우지 않는 CLI 입니다. 다만 `verify` 는 넘겨 받은 두 파일을 실제로 실행하므로(네트워크 연결은 막고 요청은 목 전송으로 잡습니다) **신뢰하는 코드에만** 사용하세요. / This tool is a CLI and does not run a network server. `verify` does execute the two files you pass it (network connections are blocked and requests go to a mocked transport), so use it **only on code you trust**.
