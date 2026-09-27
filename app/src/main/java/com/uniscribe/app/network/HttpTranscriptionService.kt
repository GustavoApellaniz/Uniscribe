package com.uniscribe.app.network

import org.json.JSONException
import org.json.JSONObject
import java.io.File
import java.io.IOException
import java.net.ConnectException
import java.net.HttpURLConnection
import java.net.MalformedURLException
import java.net.NoRouteToHostException
import java.net.SocketTimeoutException
import java.net.URL
import java.net.UnknownHostException
import java.util.UUID

internal fun buildMultipartPrefix(boundary: String, lectureId: String, safeName: String): String {
    return buildString {
        // Every part, including the audio part, starts with its own
        // delimiter. Without this line the previous field consumes the
        // audio headers and bytes.
        append(multipartField(boundary, "lecture_id", lectureId))
        append(multipartField(boundary, "title", "Nova aula"))
        append(multipartField(boundary, "language_tag", "pt-BR"))
        append("--").append(boundary).append("\r\n")
        append("Content-Disposition: form-data; name=\"audio\"; filename=\"")
        append(safeName).append("\"\r\n")
        append("Content-Type: audio/mp4\r\n\r\n")
    }
}

private fun multipartField(boundary: String, name: String, value: String): String {
    return "--$boundary\r\n" +
        "Content-Disposition: form-data; name=\"$name\"\r\n\r\n" +
        "$value\r\n"
}

/** An endpoint is supplied by the build/deployment, never selected by the UI. */
class HttpTranscriptionService(
    configuredEndpoint: String,
    private val requestHeaders: Map<String, String> = emptyMap(),
    private val authTokenProvider: () -> String? = { null },
    private val connectTimeoutMillis: Int = 15_000,
    private val readTimeoutMillis: Int = 60_000
) : TranscriptionService {

    private val endpoint: URL? = parseEndpoint(configuredEndpoint)

    override fun transcribe(audioFile: File): TranscriptionResult {
        if (!audioFile.isFile || audioFile.length() == 0L) {
            throw IOException("The recording is empty or unavailable.")
        }

        val target = endpoint
            ?: throw BackendConfigurationException("A transcription endpoint is required.")

        val connection = (target.openConnection() as? HttpURLConnection)
            ?: throw IOException("The configured endpoint does not support HTTP.")

        try {
            connection.requestMethod = "POST"
            connection.connectTimeout = connectTimeoutMillis
            connection.readTimeout = readTimeoutMillis
            connection.doOutput = true
            connection.useCaches = false
            connection.setRequestProperty("Accept", "application/json")
            requestHeaders.forEach { (name, value) ->
                connection.setRequestProperty(name, value)
            }
            authTokenProvider()?.trim()?.takeIf { it.isNotEmpty() }?.let { token ->
                connection.setRequestProperty("Authorization", "Bearer $token")
            }

            val boundary = "----UniScribe${UUID.randomUUID().toString().replace("-", "")}" 
            val lectureId = UUID.randomUUID().toString()
            val safeName = safeFileName(audioFile.name)
            val prefix = buildMultipartPrefix(boundary, lectureId, safeName)
            val suffix = "\r\n--$boundary--\r\n"
            val contentLength = prefix.toByteArray(Charsets.UTF_8).size.toLong() +
                audioFile.length() + suffix.toByteArray(Charsets.UTF_8).size
            connection.setRequestProperty(
                "Content-Type",
                "multipart/form-data; boundary=$boundary"
            )
            connection.setFixedLengthStreamingMode(contentLength)

            connection.outputStream.use { output ->
                writeUtf8(output, prefix)
                audioFile.inputStream().use { input ->
                    input.copyTo(output)
                }
                writeUtf8(output, suffix)
            }

            val responseCode = connection.responseCode
            val responseStream = if (responseCode in 200..299) {
                connection.inputStream
            } else {
                connection.errorStream
            }
            val responseBody = responseStream
                ?.bufferedReader(Charsets.UTF_8)
                ?.use { it.readText() }
                .orEmpty()

            if (responseCode !in 200..299) {
                throw IOException("The transcription backend returned HTTP $responseCode.")
            }

            return parseResponse(responseBody)
        } catch (error: BackendConfigurationException) {
            throw error
        } catch (error: UnknownHostException) {
            throw BackendUnavailableException(error)
        } catch (error: ConnectException) {
            throw BackendUnavailableException(error)
        } catch (error: NoRouteToHostException) {
            throw BackendUnavailableException(error)
        } catch (error: SocketTimeoutException) {
            throw BackendUnavailableException(error)
        } finally {
            connection.disconnect()
        }
    }

    private fun parseResponse(body: String): TranscriptionResult {
        val trimmedBody = body.trim()
        if (trimmedBody.isEmpty()) {
            throw IOException("The transcription backend returned an empty response.")
        }

        return try {
            val root = JSONObject(trimmedBody)
            val data = root.optJSONObject("data")
            val transcript = firstNonBlank(data, root, "transcript", "text", "raw_transcript", "transcript_text")
            val summary = firstNonBlank(data, root, "summary", "summary_text", "final_summary")

            if (transcript.isEmpty() && summary.isEmpty()) {
                throw IOException("The transcription backend returned no text.")
            }
            TranscriptionResult(transcript = transcript, summary = summary)
        } catch (error: JSONException) {
            // A configured backend may intentionally return plain text. Keep the
            // response honest and treat it as the transcript rather than inventing
            // a provider-specific JSON shape.
            TranscriptionResult(transcript = trimmedBody)
        }
    }

    private fun firstNonBlank(
        primary: JSONObject?,
        secondary: JSONObject,
        vararg keys: String
    ): String {
        for (key in keys) {
            val value = primary?.stringValue(key).orEmpty()
            if (value.isNotEmpty()) return value
        }
        for (key in keys) {
            val value = secondary.stringValue(key)
            if (value.isNotEmpty()) return value
        }
        return ""
    }

    private fun JSONObject.stringValue(key: String): String {
        if (!has(key) || isNull(key)) return ""
        // Structured response fields are objects/arrays. Do not serialise the
        // whole JSON object and accidentally display it as the transcript.
        val value = opt(key)
        return (value as? String)?.trim().orEmpty()
    }

    private fun writeUtf8(output: java.io.OutputStream, value: String) {
        output.write(value.toByteArray(Charsets.UTF_8))
    }

    private fun safeFileName(fileName: String): String {
        return fileName.replace("\"", "_").replace("\r", "_").replace("\n", "_")
    }

    private fun parseEndpoint(value: String): URL? {
        val trimmed = value.trim()
        if (trimmed.isEmpty()) {
            return null
        }
        return try {
            val url = URL(trimmed)
            if (url.protocol == "http" || url.protocol == "https") url else null
        } catch (_: MalformedURLException) {
            null
        }
    }
}

class BackendConfigurationException(message: String) : IOException(message)

class BackendUnavailableException(cause: Throwable) : IOException(
    "The transcription backend is unavailable.",
    cause
)
