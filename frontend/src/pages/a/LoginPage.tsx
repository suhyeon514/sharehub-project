import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"

export default function LoginPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4">
      <Card className="w-full max-w-md shadow-sm">
        <CardHeader className="space-y-2 text-center">
          <div className="mx-auto mb-2 flex h-12 w-12 items-center justify-center rounded-xl bg-[#0F6E56] text-xl font-bold text-white">
            S
          </div>

          <CardTitle className="text-2xl font-bold text-gray-900">
            ShareHub
          </CardTitle>

          <CardDescription>
            사내 자료공유 서비스에 로그인하세요.
          </CardDescription>
        </CardHeader>

        <CardContent>
          <form
            className="space-y-4"
            onSubmit={(event) => event.preventDefault()}
          >
            <div className="space-y-2">
              <label
                htmlFor="username"
                className="text-sm font-medium text-gray-700"
              >
                아이디
              </label>

              <Input
                id="username"
                type="text"
                placeholder="아이디를 입력하세요"
                autoComplete="username"
              />
            </div>

            <div className="space-y-2">
              <label
                htmlFor="password"
                className="text-sm font-medium text-gray-700"
              >
                비밀번호
              </label>

              <Input
                id="password"
                type="password"
                placeholder="비밀번호를 입력하세요"
                autoComplete="current-password"
              />
            </div>

            <Button
              type="submit"
              className="w-full bg-[#0F6E56] text-white hover:bg-[#0C5B47]"
            >
              로그인
            </Button>
          </form>

          <p className="mt-6 text-center text-xs text-gray-500">
            사내 계정으로 로그인해 주세요.
          </p>
        </CardContent>
      </Card>
    </div>
  )
}