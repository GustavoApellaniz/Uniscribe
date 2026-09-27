package com.uniscribe.app.network

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class HttpTranscriptionServiceTest {
    @Test
    fun multipartPrefixDelimitsAudioPart() {
        val prefix = buildMultipartPrefix("BOUNDARY", "lecture-1", "audio.m4a")

        assertTrue(prefix.contains("name=\"lecture_id\""))
        assertTrue(prefix.contains("name=\"language_tag\""))
        assertTrue(
            prefix.contains(
                "pt-BR\r\n--BOUNDARY\r\nContent-Disposition: form-data; name=\"audio\""
            )
        )
        assertFalse(prefix.contains("pt-BR\r\nContent-Disposition: form-data; name=\"audio\""))
    }
}
