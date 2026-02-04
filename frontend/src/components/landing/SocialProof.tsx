'use client'

export function SocialProof() {
  const testimonials = [
    {
      quote: "PISAMA caught a loop in our QA agent that would have cost us $3K in production. Paid for itself on day one.",
      author: "Alex Chen",
      title: "CTO @ AgentCo",
    },
    {
      quote: "We integrated PISAMA into CI/CD. Now every PR is tested for multi-agent failures before merge. Game changer.",
      author: "Sarah Rodriguez",
      title: "Lead Engineer @ MultiAgent Labs",
    },
    {
      quote: "The loop detection alone is worth it. But the state validation and persona drift detection are what keep our agent system reliable.",
      author: "Marcus Kim",
      title: "Founder @ AI Support Tool",
    },
  ]

  const stats = [
    { icon: "🏢", label: "50+ companies using PISAMA" },
    { icon: "⭐", label: "1.2K+ GitHub stars" },
    { icon: "🧪", label: "730K+ traces analyzed" },
    { icon: "💰", label: "$250K+ API costs prevented" },
  ]

  return (
    <section className="py-20 px-4 bg-slate-900/50">
      <div className="max-w-7xl mx-auto">
        {/* Testimonials */}
        <div className="grid md:grid-cols-3 gap-8 mb-16">
          {testimonials.map((testimonial, index) => (
            <div
              key={index}
              className="bg-slate-800/50 border border-slate-700 rounded-xl p-6 hover:border-sky-500/50 transition-colors"
            >
              <div className="text-slate-300 mb-4 leading-relaxed">
                "{testimonial.quote}"
              </div>
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-slate-700 flex items-center justify-center text-slate-400 font-semibold">
                  {testimonial.author.charAt(0)}
                </div>
                <div>
                  <div className="text-white font-medium text-sm">
                    {testimonial.author}
                  </div>
                  <div className="text-slate-400 text-xs">
                    {testimonial.title}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Stats Bar */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
          {stats.map((stat, index) => (
            <div
              key={index}
              className="text-center"
            >
              <div className="text-3xl mb-2">{stat.icon}</div>
              <div className="text-slate-400 text-sm">{stat.label}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
