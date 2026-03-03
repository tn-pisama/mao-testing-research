'use client'

import { Layout } from '@/components/common/Layout'

export default function TermsPage() {
  return (
    <Layout>
      <div className="p-6 max-w-4xl mx-auto">
        <div className="prose prose-invert prose-slate max-w-none">
          <h1 className="text-3xl font-bold text-white mb-2">Terms of Service</h1>
          <p className="text-zinc-400 text-sm mb-8">Effective Date: December 29, 2024</p>

          <section className="mb-8">
            <h2 className="text-xl font-semibold text-white mb-4">1. Acceptance of Terms</h2>
            <p className="text-zinc-300">
              By accessing or using our Service, you agree to be bound by these Terms of Service. 
              If you are using the Service on behalf of an organization, you represent that you have 
              authority to bind that organization to these Terms.
            </p>
          </section>

          <section className="mb-8">
            <h2 className="text-xl font-semibold text-white mb-4">2. Description of Service</h2>
            <p className="text-zinc-300">
              We provide a cloud-based platform for analysis and monitoring of automated systems and 
              workflows. The Service includes APIs, software development kits, documentation, and 
              related tools.
            </p>
          </section>

          <section className="mb-8">
            <h2 className="text-xl font-semibold text-white mb-4">3. Account Registration and Security</h2>
            <p className="text-zinc-300 mb-3">
              <strong className="text-white">Registration.</strong> You must provide accurate information 
              when creating an account. You are responsible for maintaining the confidentiality of your 
              account credentials.
            </p>
            <p className="text-zinc-300 mb-3">
              <strong className="text-white">Authorized Users.</strong> You may grant access to authorized 
              users within your organization. You remain responsible for all activities under your account.
            </p>
            <p className="text-zinc-300">
              <strong className="text-white">Account Security.</strong> You must notify us immediately of 
              any unauthorized use of your account or any other security breach.
            </p>
          </section>

          <section className="mb-8">
            <h2 className="text-xl font-semibold text-white mb-4">4. Data Ownership and Processing</h2>
            <p className="text-zinc-300 mb-3">
              <strong className="text-white">Your Data.</strong> You retain all right, title, and interest 
              in the data you submit to the Service (&quot;Customer Data&quot;). We do not claim ownership of 
              Customer Data.
            </p>
            <p className="text-zinc-300 mb-3">
              <strong className="text-white">Limited License.</strong> You grant us a non-exclusive, 
              royalty-free license to use Customer Data solely to provide the Service to you, including 
              storage, analysis, and generation of insights. We will not use Customer Data to train 
              machine learning models or algorithms.
            </p>
            <p className="text-zinc-300 mb-3">
              <strong className="text-white">Data Isolation.</strong> We maintain logical separation of 
              Customer Data from other customers&apos; data through technical and administrative controls.
            </p>
            <p className="text-zinc-300">
              <strong className="text-white">Data Retention.</strong> We retain Customer Data for the 
              duration of the Service Term. Upon termination, we will delete Customer Data within thirty 
              (30) days, except as required by applicable law.
            </p>
          </section>

          <section className="mb-8">
            <h2 className="text-xl font-semibold text-white mb-4">5. Intellectual Property Rights</h2>
            <p className="text-zinc-300 mb-3">
              <strong className="text-white">Our IP.</strong> The Service, including all software, 
              algorithms, methodologies, and technology, is our proprietary property. You receive only 
              a limited license to use the Service as expressly permitted by these Terms.
            </p>
            <p className="text-zinc-300 mb-3">
              <strong className="text-white">Feedback.</strong> Any suggestions, feedback, or improvements 
              you provide regarding the Service may be used by us without restriction or compensation.
            </p>
            <p className="text-zinc-300">
              <strong className="text-white">Restrictions.</strong> You may not reverse engineer, decompile, 
              or attempt to extract the source code of the Service or underlying algorithms.
            </p>
          </section>

          <section className="mb-8">
            <h2 className="text-xl font-semibold text-white mb-4">6. AI-Generated Content and Suggestions</h2>
            <p className="text-zinc-300 mb-3">
              <strong className="text-white">Nature of AI Output.</strong> The Service may generate 
              automated suggestions, recommendations, or other content using artificial intelligence 
              (&quot;AI Output&quot;). AI Output is provided for informational purposes only.
            </p>
            <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-4 mb-3">
              <p className="text-amber-200 font-medium mb-2">NO WARRANTIES ON AI OUTPUT</p>
              <p className="text-amber-200/80 text-sm">
                We make no warranties regarding the accuracy, reliability, or appropriateness of AI Output. 
                AI Output may contain errors, inaccuracies, or biases.
              </p>
            </div>
            <p className="text-zinc-300 mb-3">
              <strong className="text-white">Your Responsibility.</strong> You are solely responsible for 
              reviewing, validating, and determining the appropriateness of any AI Output before 
              implementation or use.
            </p>
            <p className="text-zinc-300">
              <strong className="text-white">No Professional Advice.</strong> AI Output does not constitute 
              professional advice and should not be relied upon as such.
            </p>
          </section>

          <section className="mb-8">
            <h2 className="text-xl font-semibold text-white mb-4">7. Security</h2>
            <p className="text-zinc-300 mb-3">
              <strong className="text-white">Security Measures.</strong> We implement reasonable 
              administrative, physical, and technical safeguards designed to protect Customer Data 
              against unauthorized access, use, modification, or disclosure.
            </p>
            <p className="text-zinc-300 mb-3">
              <strong className="text-white">No Security Guarantee.</strong> We do not guarantee that 
              the Service will be free from security vulnerabilities or that Customer Data will be 
              completely secure from unauthorized access.
            </p>
            <p className="text-zinc-300">
              <strong className="text-white">Customer Responsibilities.</strong> You are responsible for 
              maintaining confidentiality of account credentials, promptly notifying us of any suspected 
              unauthorized access, and implementing appropriate security measures for your systems.
            </p>
          </section>

          <section className="mb-8">
            <h2 className="text-xl font-semibold text-white mb-4">8. Confidentiality</h2>
            <p className="text-zinc-300 mb-3">
              Each party acknowledges it may receive confidential information from the other party. 
              Our confidential information includes the Service&apos;s features, functionality, algorithms, 
              performance metrics, and any non-public aspects of the platform.
            </p>
            <p className="text-zinc-300">
              Each party will maintain confidentiality of the other party&apos;s confidential information, 
              use such information solely for purposes of this Agreement, and not disclose such 
              information to third parties without prior written consent, except as required by law.
            </p>
          </section>

          <section className="mb-8">
            <h2 className="text-xl font-semibold text-white mb-4">9. Acceptable Use</h2>
            <p className="text-zinc-300 mb-3">You may not use the Service to:</p>
            <ul className="list-disc list-inside text-zinc-300 space-y-1">
              <li>Violate any applicable laws or regulations</li>
              <li>Infringe on intellectual property rights</li>
              <li>Transmit malware or harmful code</li>
              <li>Attempt to gain unauthorized access to our systems</li>
              <li>Use the Service for competitive analysis or to develop competing products</li>
              <li>Submit false, misleading, or deceptive data</li>
            </ul>
          </section>

          <section className="mb-8">
            <h2 className="text-xl font-semibold text-white mb-4">10. Payment Terms</h2>
            <p className="text-zinc-300 mb-3">
              You agree to pay all applicable fees according to your selected plan. Fees are 
              non-refundable except as expressly stated. Fees are billed in advance and automatically 
              charged to your payment method.
            </p>
            <p className="text-zinc-300">
              We may suspend the Service for accounts with overdue payments.
            </p>
          </section>

          <section className="mb-8">
            <h2 className="text-xl font-semibold text-white mb-4">11. Limitation of Liability</h2>
            <div className="bg-zinc-800 border border-zinc-700 rounded-lg p-4">
              <p className="text-zinc-300 mb-3">
                <strong className="text-white">DISCLAIMER OF WARRANTIES.</strong> THE SERVICE IS PROVIDED 
                &quot;AS IS&quot; WITHOUT WARRANTIES OF ANY KIND, EXPRESS OR IMPLIED.
              </p>
              <p className="text-zinc-300 mb-3">
                <strong className="text-white">LIMITATION OF LIABILITY.</strong> TO THE MAXIMUM EXTENT 
                PERMITTED BY LAW, OUR TOTAL LIABILITY ARISING FROM OR RELATING TO THE SERVICE SHALL NOT 
                EXCEED THE AMOUNTS PAID BY YOU FOR THE SERVICE IN THE TWELVE (12) MONTHS PRECEDING THE CLAIM.
              </p>
              <p className="text-zinc-300">
                <strong className="text-white">EXCLUSION OF DAMAGES.</strong> WE SHALL NOT BE LIABLE FOR 
                ANY INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, OR PUNITIVE DAMAGES, INCLUDING WITHOUT 
                LIMITATION LOSS OF PROFITS, DATA, OR BUSINESS INTERRUPTION.
              </p>
            </div>
          </section>

          <section className="mb-8">
            <h2 className="text-xl font-semibold text-white mb-4">12. Indemnification</h2>
            <p className="text-zinc-300">
              You agree to indemnify and hold us harmless from any claims, damages, or expenses arising 
              from your use of the Service, violation of these Terms, or infringement of third-party rights.
            </p>
          </section>

          <section className="mb-8">
            <h2 className="text-xl font-semibold text-white mb-4">13. Termination</h2>
            <p className="text-zinc-300 mb-3">
              <strong className="text-white">Termination by You.</strong> You may terminate your account 
              at any time by providing written notice.
            </p>
            <p className="text-zinc-300 mb-3">
              <strong className="text-white">Termination by Us.</strong> We may suspend or terminate your 
              access immediately for violation of these Terms or for any reason with thirty (30) days&apos; notice.
            </p>
            <p className="text-zinc-300">
              <strong className="text-white">Effect of Termination.</strong> Upon termination, your right 
              to use the Service ceases immediately. We will make Customer Data available for download 
              for thirty (30) days following termination.
            </p>
          </section>

          <section className="mb-8">
            <h2 className="text-xl font-semibold text-white mb-4">14. Changes to Terms</h2>
            <p className="text-zinc-300">
              We may modify these Terms by providing notice through the Service or via email. Continued 
              use of the Service after changes constitutes acceptance of the modified Terms.
            </p>
          </section>

          <section className="mb-8">
            <h2 className="text-xl font-semibold text-white mb-4">15. General Provisions</h2>
            <p className="text-zinc-300 mb-3">
              <strong className="text-white">Governing Law.</strong> These Terms are governed by the 
              laws of the State of Delaware, excluding conflict of law principles.
            </p>
            <p className="text-zinc-300 mb-3">
              <strong className="text-white">Severability.</strong> If any provision is found unenforceable, 
              the remainder of these Terms remains in effect.
            </p>
            <p className="text-zinc-300 mb-3">
              <strong className="text-white">Entire Agreement.</strong> These Terms constitute the entire 
              agreement between you and us regarding the Service.
            </p>
            <p className="text-zinc-300">
              <strong className="text-white">Assignment.</strong> You may not assign these Terms without 
              our written consent. We may assign these Terms without restriction.
            </p>
          </section>

          <section className="mb-8">
            <h2 className="text-xl font-semibold text-white mb-4">16. Contact</h2>
            <p className="text-zinc-300">
              For questions about these Terms, contact us at: <a href="mailto:legal@pisama.ai" className="text-blue-400 hover:underline">legal@pisama.ai</a>
            </p>
          </section>

          <div className="mt-12 pt-8 border-t border-zinc-700">
            <p className="text-zinc-500 text-sm">
              Pisama Oy &middot; Last Updated: December 29, 2024
            </p>
          </div>
        </div>
      </div>
    </Layout>
  )
}
