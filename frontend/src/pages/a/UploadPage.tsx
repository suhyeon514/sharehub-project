import { useState } from "react"
import { useNavigate } from "react-router-dom"

import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Input } from "@/components/ui/input"

type Visibility = "private" | "team"

export default function UploadPage() {
  const navigate = useNavigate()

  const [title, setTitle] = useState("")
  const [visibility, setVisibility] = useState<Visibility>("private")
  const [description, setDescription] = useState("")
  const [selectedFile, setSelectedFile] = useState<File | null>(null)

  const [isSubmitting, setIsSubmitting] = useState(false)
  const [errorMessage, setErrorMessage] = useState("")

  const handleSubmit = async (
    event: React.FormEvent<HTMLFormElement>,
  ) => {
    event.preventDefault()

    setErrorMessage("")

    if (!title.trim()) {
      setErrorMessage("자료 제목을 입력해주세요.")
      return
    }

    if (!selectedFile) {
      setErrorMessage("업로드할 파일을 선택해주세요.")
      return
    }

    const token = localStorage.getItem("sharehub_token")

    if (!token) {
      navigate("/login")
      return
    }

    const formData = new FormData()

    formData.append("title", title.trim())
    formData.append("visibility", visibility)
    formData.append("description", description.trim())
    formData.append("file", selectedFile)

    try {
      setIsSubmitting(true)

      const response = await fetch("/api/documents", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
        },
        body: formData,
      })

      const data = await response.json().catch(() => null)

      if (response.status === 401) {
        localStorage.removeItem("sharehub_token")
        localStorage.removeItem("sharehub_user")
        localStorage.removeItem("sharehub_expires_at")

        navigate("/login")
        return
      }

      if (!response.ok) {
        const message =
          data?.message ??
          data?.error ??
          "자료 업로드에 실패했습니다."

        setErrorMessage(message)
        return
      }

      navigate("/documents/mine")
    } catch (error) {
      console.error("document upload failed:", error)

      setErrorMessage(
        "서버와 통신할 수 없습니다. 잠시 후 다시 시도해주세요.",
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleCancel = () => {
    navigate("/documents/mine")
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">
          자료 업로드
        </h2>

        <p className="mt-1 text-sm text-gray-500">
          ShareHub에 새로운 자료를 등록합니다.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">
            자료 정보
          </CardTitle>

          <CardDescription>
            업로드할 자료의 기본 정보를 입력하세요.
          </CardDescription>
        </CardHeader>

        <CardContent>
          <form
            className="space-y-6"
            onSubmit={handleSubmit}
          >
            {/* 자료 제목 */}
            <div className="space-y-2">
              <label
                htmlFor="title"
                className="text-sm font-medium text-gray-700"
              >
                자료 제목
              </label>

              <Input
                id="title"
                type="text"
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                placeholder="자료 제목을 입력하세요"
                disabled={isSubmitting}
              />
            </div>

            {/* 공개 범위 */}
            <div className="space-y-2">
              <label
                htmlFor="visibility"
                className="text-sm font-medium text-gray-700"
              >
                공개 범위
              </label>

              <select
                id="visibility"
                value={visibility}
                onChange={(event) =>
                  setVisibility(
                    event.target.value as Visibility,
                  )
                }
                disabled={isSubmitting}
                className="h-9 w-full rounded-md border border-gray-200 bg-white px-3 text-sm outline-none transition focus:border-[#0F6E56] focus:ring-2 focus:ring-[#0F6E56]/10 disabled:cursor-not-allowed disabled:opacity-60"
              >
                <option value="private">
                  비공개 - 나만 볼 수 있음
                </option>

                <option value="team">
                  팀 공개 - 같은 부서 사용자
                </option>
              </select>
            </div>

            {/* 자료 설명 */}
            <div className="space-y-2">
              <label
                htmlFor="description"
                className="text-sm font-medium text-gray-700"
              >
                자료 설명
              </label>

              <textarea
                id="description"
                value={description}
                onChange={(event) =>
                  setDescription(event.target.value)
                }
                placeholder="자료에 대한 간단한 설명을 입력하세요"
                rows={5}
                disabled={isSubmitting}
                className="w-full resize-none rounded-md border border-gray-200 bg-white px-3 py-2 text-sm outline-none transition placeholder:text-gray-400 focus:border-[#0F6E56] focus:ring-2 focus:ring-[#0F6E56]/10 disabled:cursor-not-allowed disabled:opacity-60"
              />
            </div>

            {/* 파일 선택 */}
            <div className="space-y-2">
              <label
                htmlFor="file"
                className="text-sm font-medium text-gray-700"
              >
                파일
              </label>

              <div className="rounded-lg border border-dashed border-gray-300 bg-gray-50 p-6">
                <Input
                  id="file"
                  type="file"
                  disabled={isSubmitting}
                  onChange={(event) =>
                    setSelectedFile(
                      event.target.files?.[0] ?? null,
                    )
                  }
                  className="bg-white"
                />

                <p className="mt-2 text-xs text-gray-500">
                  업로드할 파일을 선택하세요.
                </p>
              </div>

              {selectedFile && (
                <div className="rounded-lg bg-gray-50 px-4 py-3">
                  <p className="text-sm font-medium text-gray-800">
                    {selectedFile.name}
                  </p>

                  <p className="mt-1 text-xs text-gray-500">
                    {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
                  </p>
                </div>
              )}
            </div>

            {/* 에러 메시지 */}
            {errorMessage && (
              <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3">
                <p className="text-sm text-red-700">
                  {errorMessage}
                </p>
              </div>
            )}

            {/* 버튼 */}
            <div className="flex justify-end gap-3 border-t pt-6">
              <Button
                type="button"
                variant="outline"
                onClick={handleCancel}
                disabled={isSubmitting}
              >
                취소
              </Button>

              <Button
                type="submit"
                disabled={isSubmitting}
                className="bg-[#0F6E56] text-white hover:bg-[#0C5B47]"
              >
                {isSubmitting
                  ? "업로드 중..."
                  : "자료 업로드"}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}